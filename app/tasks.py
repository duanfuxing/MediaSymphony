from celery import shared_task
from app.routers.video_tasks import TaskStatus, tasks_db, AudioMode
from app.services.video_scene_split.server.api_server import SceneDetector
from app.services.audio_separation.routes import separate_audio
from app.services.audio_transcription.routes import transcribe_audio
from app.config import settings
from app.utils.logger import Logger
import os
import asyncio
import httpx
from datetime import datetime
import json

logger = Logger("celery_tasks")


def get_file_extension(url: str, content_type: str) -> str:
    """获取文件扩展名

    优先从URL中获取扩展名，如果URL中没有扩展名则从content_type中判断

    Args:
        url (str): 文件URL
        content_type (str): HTTP响应头中的Content-Type

    Returns:
        str: 文件扩展名（包含点号）
    """
    # 1. 尝试从URL中获取扩展名
    url_ext = os.path.splitext(url)[1].lower()
    if url_ext and len(url_ext) < 6:  # 防止异常的长扩展名
        return url_ext

    # 2. 从content_type中判断扩展名
    type_ext_map = {
        "video/mp4": ".mp4",
        "video/x-msvideo": ".avi",
        "video/quicktime": ".mov",
        "video/x-matroska": ".mkv",
        "video/webm": ".webm",
    }
    return type_ext_map.get(content_type.lower(), ".mp4")  # 默认使用.mp4


async def download_video(video_url: str, save_path: str) -> None:
    """从URL下载视频文件

    Args:
        video_url (str): 视频URL
        save_path (str): 保存路径

    Raises:
        Exception: 下载失败时抛出异常
    """
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", video_url) as response:
                response.raise_for_status()
                # 获取正确的文件扩展名
                ext = get_file_extension(
                    video_url, response.headers.get("content-type", "")
                )
                # 更新保存路径的扩展名
                save_path = os.path.splitext(save_path)[0] + ext
                async with open(save_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
                return save_path
    except Exception as e:
        logger.error(f"视频下载失败: {str(e)}", {"video_url": video_url})
        raise


async def update_task_status_and_log(
    task_id: str, status: TaskStatus, extra_info: dict = None
):
    """更新任务状态并记录日志

    Args:
        task_id (str): 任务ID
        status (TaskStatus): 任务状态
        extra_info (dict, optional): 额外的日志信息
    """
    tasks_db.update_task_status(task_id, status)
    logger.log_task_status(task_id, status, extra_info)


async def update_task_step(
    task_id: str, step: str, status: str, output: str = None, error: str = None
):
    """更新任务步骤状态和输出

    用于更新视频处理任务的各个步骤状态，包括文件上传、场景分割、音频分离等过程的状态信息。
    每个步骤可以包含成功/失败状态、输出结果和错误信息。

    Args:
        task_id (str): 任务ID，用于唯一标识一个处理任务
        step (str): 步骤名称，如'upload'、'scene_cut'、'audio_extract'等
        status (str): 步骤状态，可以是'processing'、'success'、'failed'等
        output (str, optional): 步骤输出结果，如上传后的文件路径、处理结果等
        error (str, optional): 错误信息，当步骤失败时的详细错误说明

    Note:
        该函数会将步骤信息更新到数据库中，用于前端展示和状态追踪
    """
    tasks_db.update_task_step_and_output(task_id, step, status, output, error)


async def prepare_directories(task_id: str) -> tuple[str, str]:
    """准备任务所需的目录结构

    Args:
        task_id (str): 任务ID

    Returns:
        tuple[str, str]: 上传目录和输出目录的路径
    """
    now = datetime.now()
    upload_dir = os.path.join(
        settings.UPLOAD_DIR, str(now.year), f"{now.month:02d}", task_id
    )
    output_path = os.path.join(
        settings.PROCESSED_DIR, str(now.year), f"{now.month:02d}", task_id
    )
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(output_path, exist_ok=True)
    return upload_dir, output_path


async def handle_scene_detection(
    task_id: str, video_path: str, output_path: str, video_split_audio_mode: str
) -> list:
    """处理场景分割任务

    Args:
        task_id (str): 任务ID
        video_path (str): 视频文件路径
        output_path (str): 输出目录路径
        video_split_audio_mode (str): 音频处理模式

    Returns:
        list: 场景分割结果列表

    Raises:
        Exception: 场景分割失败时抛出异常
    """
    try:
        logger.info(
            "开始场景分割", {"task_id": task_id, "audio_mode": video_split_audio_mode}
        )
        await update_task_step(task_id, "scene_cut", "processing")
        detector = SceneDetector(port=settings.SCENE_DETECTION_API_PORT)

        scenes = []
        if video_split_audio_mode in [AudioMode.BOTH, AudioMode.UNMUTE]:
            unmute_scenes = await asyncio.wait_for(
                detector.process_video(
                    video_path, output_path, audio_mode=AudioMode.UNMUTE
                ),
                timeout=settings.SCENE_DETECTION_TIMEOUT,
            )
            scenes.extend(unmute_scenes)
            logger.info(
                "有声场景分割完成",
                {"task_id": task_id, "scenes_count": len(unmute_scenes)},
            )

        if video_split_audio_mode in [AudioMode.BOTH, AudioMode.MUTE]:
            mute_scenes = await asyncio.wait_for(
                detector.process_video(
                    video_path, output_path, audio_mode=AudioMode.MUTE
                ),
                timeout=settings.SCENE_DETECTION_TIMEOUT,
            )
            scenes.extend(mute_scenes)
            logger.info(
                "静音场景分割完成",
                {"task_id": task_id, "scenes_count": len(mute_scenes)},
            )

        scenes.sort(key=lambda x: x.get("start_frame", 0))
        await update_task_step(task_id, "scene_cut", "success", json.dumps(scenes))
        logger.info(
            "场景分割全部完成", {"task_id": task_id, "total_scenes_count": len(scenes)}
        )
        return scenes

    except Exception as e:
        error_msg = str(e)
        await update_task_step(task_id, "scene_cut", "failed", error=error_msg)
        logger.error("场景分割失败", {"task_id": task_id, "error": error_msg})
        raise


async def handle_audio_separation(
    task_id: str, video_path: str, output_path: str
) -> str:
    """处理音频分离任务

    Args:
        task_id (str): 任务ID
        video_path (str): 视频文件路径
        output_path (str): 输出目录路径

    Returns:
        str: 音频文件路径

    Raises:
        Exception: 音频分离失败时抛出异常
    """
    try:
        logger.info("开始音频分离", {"task_id": task_id})
        await update_task_step(task_id, "audio_extract", "processing")
        audio_path = await asyncio.wait_for(
            separate_audio(video_path, output_path),
            timeout=settings.AUDIO_SEPARATION_TIMEOUT,
        )
        await update_task_step(task_id, "audio_extract", "success", audio_path)
        logger.info("音频分离完成", {"task_id": task_id, "audio_path": audio_path})
        return audio_path

    except Exception as e:
        error_msg = str(e)
        await update_task_step(task_id, "audio_extract", "failed", error=error_msg)
        logger.error("音频分离失败", {"task_id": task_id, "error": error_msg})
        raise


async def handle_audio_transcription(
    task_id: str, video_path: str, output_path: str
) -> str:
    """处理语音转写任务

    Args:
        task_id (str): 任务ID
        video_path (str): 视频文件路径
        output_path (str): 输出目录路径

    Returns:
        str: 转写结果

    Raises:
        Exception: 语音转写失败时抛出异常
    """
    try:
        logger.info("开始语音转写", {"task_id": task_id})
        await update_task_step(task_id, "text_convert", "processing")
        transcription = await asyncio.wait_for(
            transcribe_audio(video_path, output_path),
            timeout=settings.AUDIO_TRANSCRIPTION_TIMEOUT,
        )
        await update_task_step(task_id, "text_convert", "success", transcription)
        logger.info("语音转写完成", {"task_id": task_id})
        return transcription

    except Exception as e:
        error_msg = str(e)
        await update_task_step(task_id, "text_convert", "failed", error=error_msg)
        logger.error("语音转写失败", {"task_id": task_id, "error": error_msg})
        raise


async def cleanup_temp_files(task_id: str, video_path: str, audio_path: str):
    """清理临时文件

    Args:
        task_id (str): 任务ID
        video_path (str): 视频文件路径
        audio_path (str): 音频文件路径
    """
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        logger.info("临时文件清理完成", {"task_id": task_id})
    except Exception as e:
        logger.error("临时文件清理失败", {"task_id": task_id, "error": str(e)})


async def upload_audio_file(
    audio_path: str, base_path: str, uid: str, task_id: str
) -> str:
    """上传音频文件到对象存储

    Args:
        audio_path (str): 音频文件本地路径
        base_path (str): 基础存储路径
        uid (str): 用户ID
        task_id (str): 任务ID

    Returns:
        str: 音频文件的对象存储路径

    Raises:
        Exception: 上传失败时抛出异常
    """
    try:
        tos_client = TOSClient()
        audio_object_key = f"{base_path}/audio.mp3"
        tos_client.upload_file(
            local_file_path=audio_path,
            object_key=audio_object_key,
            metadata={"uid": uid, "task_id": task_id},
        )
        return audio_object_key
    except Exception as e:
        logger.error("音频文件上传失败", {"task_id": task_id, "error": str(e)})
        raise


async def upload_transcription_file(
    transcription: str, output_path: str, base_path: str, uid: str, task_id: str
) -> str:
    """上传转写文件到对象存储

    Args:
        transcription (str): 转写内容
        output_path (str): 输出目录路径
        base_path (str): 基础存储路径
        uid (str): 用户ID
        task_id (str): 任务ID

    Returns:
        str: 转写文件的对象存储路径

    Raises:
        Exception: 上传失败时抛出异常
    """
    try:
        tos_client = TOSClient()
        transcription_object_key = f"{base_path}/transcription.txt"
        transcription_path = os.path.join(output_path, "transcription.txt")

        with open(transcription_path, "w") as f:
            f.write(transcription)

        tos_client.upload_file(
            local_file_path=transcription_path,
            object_key=transcription_object_key,
            metadata={"uid": uid, "task_id": task_id},
        )
        return transcription_object_key
    except Exception as e:
        logger.error("转写文件上传失败", {"task_id": task_id, "error": str(e)})
        raise


async def upload_scene_files(
    scenes: list, base_path: str, uid: str, task_id: str
) -> list:
    """上传场景切割文件到对象存储

    Args:
        scenes (list): 场景切割结果列表
        base_path (str): 基础存储路径
        uid (str): 用户ID
        task_id (str): 任务ID

    Returns:
        list: 场景文件信息列表

    Raises:
        Exception: 上传失败时抛出异常
    """
    try:
        tos_client = TOSClient()
        scene_files = []

        for i, scene in enumerate(scenes):
            scene_type = "mute_scenes" if scene.get("is_mute") else "unmute_scenes"
            scene_path = scene.get("output_path")

            if scene_path and os.path.exists(scene_path):
                scene_object_key = f"{base_path}/{scene_type}/{i}.mp4"
                tos_client.upload_file(
                    local_file_path=scene_path,
                    object_key=scene_object_key,
                    metadata={"uid": uid, "task_id": task_id, "scene_index": i},
                )
                scene_files.append(
                    {
                        "index": i,
                        "type": scene_type,
                        "object_key": scene_object_key,
                        "start_frame": scene.get("start_frame"),
                        "end_frame": scene.get("end_frame"),
                        "is_mute": scene.get("is_mute"),
                    }
                )

        return scene_files
    except Exception as e:
        logger.error("场景文件上传失败", {"task_id": task_id, "error": str(e)})
        raise


@shared_task(bind=True, name="app.tasks.process_video")
async def process_video(
    self,
    task_id: str,
    video_url: str,
    uid: str,
    video_split_audio_mode: str = AudioMode.BOTH,
):
    """处理视频的异步任务

    该任务执行以下步骤：
    1. 视频场景分割
    2. 音频分离
    3. 语音转写

    Args:
        self: Celery任务实例
        task_id (str): 任务ID
        video_url (str): 视频URL
        uid (str): 用户ID
        video_split_audio_mode (str): 音频处理模式

    Returns:
        dict: 包含场景分割和语音转写结果的字典

    Raises:
        Exception: 当任何子任务失败或超时时抛出异常
    """
    logger.info(
        "开始处理视频任务", {"task_id": task_id, "uid": uid, "video_url": video_url}
    )
    try:
        # 1. 更新任务状态为处理中
        await update_task_status_and_log(task_id, TaskStatus.PROCESSING)

        # 2. 准备目录结构
        upload_dir, output_path = await prepare_directories(task_id)

        # 3. 下载视频文件
        video_path = os.path.join(upload_dir, "origin")
        logger.info("开始下载视频", {"task_id": task_id, "video_url": video_url})
        video_path = await download_video(video_url, video_path)
        logger.info("视频下载完成", {"task_id": task_id, "video_path": video_path})

        # 4. 串行执行子任务
        scenes = await handle_scene_detection(
            task_id, video_path, output_path, video_split_audio_mode
        )
        audio_path = await handle_audio_separation(task_id, video_path, output_path)
        transcription = await handle_audio_transcription(
            task_id, video_path, output_path
        )

        # 5. 上传结果到对象存储
        now = datetime.now()
        base_path = f"videos/{now.year}/{now.month:02d}/{task_id}"

        # 5-1. 上传音频文件
        audio_object_key = await upload_audio_file(audio_path, base_path, uid, task_id)

        # 5-2. 上传转写文件
        transcription_object_key = await upload_transcription_file(
            transcription, output_path, base_path, uid, task_id
        )

        # 5-3. 上传场景切割文件
        scene_files = await upload_scene_files(scenes, base_path, uid, task_id)

        # 5-4. 更新结果中的文件路径
        result.update(
            {
                "audio_object_key": audio_object_key,
                "transcription_object_key": transcription_object_key,
                "scene_files": scene_files,
            }
        )

        # 6. 更新任务结果
        result = {
            "scenes": scenes,
            "transcription": transcription,
            "audio_path": audio_path,
            "video_path": video_path,
        }

        await update_task_step(task_id, "final_result", "success", json.dumps(result))
        await update_task_status_and_log(
            task_id, TaskStatus.COMPLETED, {"result_size": len(str(result))}
        )

        # 7. 清理临时文件
        await cleanup_temp_files(task_id, video_path, audio_path)

        return result

    except Exception as e:
        error_info = {
            "error": str(e),
            "error_time": datetime.now().isoformat(),
        }
        await update_task_status_and_log(task_id, TaskStatus.FAILED)
        await update_task_step(
            task_id, "final_result", "failed", error=json.dumps(error_info)
        )
        logger.error("任务处理失败", {"task_id": task_id, "error": error_info})
        raise
