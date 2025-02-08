from celery import shared_task
from app.routers.video_tasks import TaskStatus, tasks_db
from app.services.video_scene_split.server.api_server import SceneDetector
from app.services.audio_separation.routes import separate_audio
from app.services.audio_transcription.routes import transcribe_audio
from app.config import settings
from app.utils.logger import Logger
import os
import asyncio

logger = Logger("celery_tasks")


@shared_task(bind=True, name="app.tasks.process_video")
async def process_video(self, task_id: str, video_path: str, uid: str):
    """处理视频的异步任务

    该任务执行以下步骤：
    1. 视频场景分割
    2. 音频分离
    3. 语音转写

    Args:
        self: Celery任务实例
        task_id (str): 任务ID
        video_path (str): 视频文件路径
        uid (str): 用户ID

    Returns:
        dict: 包含场景分割和语音转写结果的字典

    Raises:
        Exception: 当任何子任务失败或超时时抛出异常
    """
    logger.info("开始处理视频任务", {"task_id": task_id, "uid": uid})
    try:
        # 更新任务状态为处理中
        tasks_db.update_task_status(task_id, TaskStatus.PROCESSING)
        logger.log_task_status(task_id, TaskStatus.PROCESSING)

        # 准备音频文件路径
        audio_path = f"data/processed/{task_id}_audio.wav"

        # 并行执行三个子任务
        tasks = [
            # 1. 场景分割任务
            async def scene_detection():
                try:
                    logger.info("开始场景分割", {"task_id": task_id})
                    tasks_db.update_task_status(task_id, "processing", "scene_cut_status")
                    detector = SceneDetector(port=settings.SCENE_DETECTION_API_PORT)
                    scenes = await asyncio.wait_for(
                        detector.process_video(video_path),
                        timeout=settings.SCENE_DETECTION_TIMEOUT,
                    )
                    tasks_db.update_task_step_and_output(
                        task_id, "scene_cut", "scene_cut_output", json.dumps(scenes)
                    )
                    tasks_db.update_task_status(task_id, "success", "scene_cut_status")
                    logger.info("场景分割完成", {"task_id": task_id, "scenes_count": len(scenes)})
                    return scenes
                except Exception as e:
                    tasks_db.update_task_status(task_id, "failed", "scene_cut_status", str(e))
                    logger.error("场景分割失败", {"task_id": task_id, "error": str(e)})
                    raise

            # 2. 音频分离任务
            async def audio_separation():
                try:
                    logger.info("开始音频分离", {"task_id": task_id})
                    tasks_db.update_task_status(task_id, "processing", "audio_extract_status")
                    await asyncio.wait_for(
                        separate_audio(
                            video_path, audio_path, port=settings.AUDIO_SEPARATION_API_PORT
                        ),
                        timeout=settings.AUDIO_SEPARATION_TIMEOUT,
                    )
                    tasks_db.update_task_step_and_output(
                        task_id, "audio_extract", "audio_extract_output", audio_path
                    )
                    tasks_db.update_task_status(task_id, "success", "audio_extract_status")
                    logger.info("音频分离完成", {"task_id": task_id, "audio_path": audio_path})
                    return audio_path
                except Exception as e:
                    tasks_db.update_task_status(task_id, "failed", "audio_extract_status", str(e))
                    logger.error("音频分离失败", {"task_id": task_id, "error": str(e)})
                    raise

            # 3. 语音转写任务
            async def audio_transcription():
                try:
                    # 等待音频分离完成
                    await audio_separation()
                    logger.info("开始语音转写", {"task_id": task_id})
                    tasks_db.update_task_status(task_id, "processing", "text_convert_status")
                    transcription = await asyncio.wait_for(
                        transcribe_audio(
                            audio_path, port=settings.AUDIO_TRANSCRIPTION_API_PORT
                        ),
                        timeout=settings.AUDIO_TRANSCRIPTION_TIMEOUT,
                    )
                    tasks_db.update_task_step_and_output(
                        task_id, "text_convert", "text_convert_output", transcription
                    )
                    tasks_db.update_task_status(task_id, "success", "text_convert_status")
                    logger.info("语音转写完成", {"task_id": task_id})
                    return transcription
                except Exception as e:
                    tasks_db.update_task_status(task_id, "failed", "text_convert_status", str(e))
                    logger.error("语音转写失败", {"task_id": task_id, "error": str(e)})
                    raise
        ]

        # 并行执行场景分割和语音转写任务（语音转写任务会自动等待音频分离完成）
        scenes, transcription = await asyncio.gather(
            scene_detection(),
            audio_transcription()
        )

        # 更新任务结果
        result = {"scenes": scenes, "transcription": transcription}
        tasks_db.update_task_status(task_id, TaskStatus.COMPLETED)
        logger.log_task_status(
            task_id, TaskStatus.COMPLETED, {"result_size": len(str(result))}
        )

        # 清理临时文件
        os.remove(video_path)
        os.remove(audio_path)
        logger.info("临时文件清理完成", {"task_id": task_id})

        return result

    except Exception as e:
        # 更新任务状态为失败
        tasks_db.update_task_status(task_id, TaskStatus.FAILED, str(e))
        logger.error("任务处理失败", {"task_id": task_id, "error": str(e)})
        raise
