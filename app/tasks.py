import aiohttp
from celery import Task
from app.celery_app import celery_app
from app.models.task_models import TaskStatus, AudioMode
from app.config import settings
from app.utils.logger import Logger
from app.utils.tos_client import TOSClient
from app.services.mysql.video_tasks_db import VideoTasksDB
import os
import asyncio
import httpx
from datetime import datetime
import shutil
import aiofiles

logger = Logger("celery_tasks")
tasks_db = VideoTasksDB()


class AsyncTask(Task):
    """异步任务的基类"""
    _is_async = True
    
    def run(self, *args, **kwargs):
        """
        重写 Task 的 run 方法，确保它可以正确处理参数
        """
        return self._process(*args, **kwargs)



def get_file_extension(url: str, content_type: str) -> str:
    """获取文件扩展名

    优先从URL中获取扩展名 如果URL中没有扩展名则从content_type中判断

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
                async with aiofiles.open(save_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
                return save_path
    except Exception as e:
        logger.error(f"视频下载失败: {str(e)}", {"video_url": video_url})
        raise


async def update_task_status_and_log(
    task_id: str, status: TaskStatus, extra_info: str = None
):
    """更新任务状态并记录日志

    Args:
        task_id (str): 任务ID
        status (TaskStatus): 任务状态
        extra_info (str, optional): 额外的错误信息
    """
    tasks_db.update_task_status(task_id, status)
    # 构建额外信息字典
    extra_dict = {"error": extra_info} if extra_info else {}
    logger.log_task_status(task_id, status, extra_dict)


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

# 准备每一次任务的目录
async def prepare_directories(task_id: str) -> tuple[str, str]:
    """准备任务所需的目录结构

    Args:
        task_id (str): 任务ID

    Returns:
        tuple[str, str]: 上传目录和输出目录的路径
    """
    try:
        now = datetime.now()
        
        output_path = os.path.join(
            settings.PROCESSED_DIR, str(now.year), f"{now.month:02d}", task_id
        )
        # 构建目录路径
        upload_dir = os.path.join(
            settings.UPLOAD_DIR, str(now.year), f"{now.month:02d}", task_id
        )
        
        # 分别处理上传目录
        try:
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir, mode=0o755, exist_ok=True)
                if not os.path.exists(upload_dir):
                    raise Exception(f"上传目录创建失败，路径: {upload_dir}")
                logger.info(f"创建上传目录成功: {upload_dir}")
        except Exception as e:
            logger.error(f"创建上传目录失败: {str(e)}", {
                "task_id": task_id,
                "upload_dir": upload_dir,
                "error": str(e)
            })
            raise

        # 分别处理输出目录
        try:
            if not os.path.exists(output_path):
                os.makedirs(output_path, mode=0o755, exist_ok=True)
                if not os.path.exists(output_path):
                    raise Exception(f"输出目录创建失败，路径: {output_path}")
                logger.info(f"创建输出目录成功: {output_path}")
        except Exception as e:
            logger.error(f"创建输出目录失败: {str(e)}", {
                "task_id": task_id,
                "output_path": output_path,
                "error": str(e)
            })
            raise

        # 分别处理保存静音视频目录
        try:
            mute_video_path = os.path.join(output_path, "mute")
            if not os.path.exists(mute_video_path):
                os.makedirs(mute_video_path, mode=0o755, exist_ok=True)
                if not os.path.exists(mute_video_path):
                    raise Exception(f"静音视频目录创建失败，路径: {mute_video_path}")
                logger.info(f"创建静音视频目录成功: {mute_video_path}")
        except Exception as e:
            logger.error(f"创建静音视频目录失败: {str(e)}", {
                "task_id": task_id,
                "output_path": mute_video_path,
                "error": str(e)
            })
            raise

        # 分别处理保存非静音视频目录
        try:
            un_mute_video_path = os.path.join(output_path, "un_mute")
            if not os.path.exists(un_mute_video_path):
                os.makedirs(un_mute_video_path, mode=0o755, exist_ok=True)
                if not os.path.exists(un_mute_video_path):
                    raise Exception(f"非静音视频目录创建失败，路径: {un_mute_video_path}")
                logger.info(f"创建非静音视频目录成功: {un_mute_video_path}")
        except Exception as e:
            logger.error(f"创建非静音视频目录失败: {str(e)}", {
                "task_id": task_id,
                "output_path": un_mute_video_path,
                "error": str(e)
            })
            raise
        # 视频封面目录
        # 分别处理保存非静音视频目录
        try:
            cover_dir = os.path.join(output_path, "cover")
            if not os.path.exists(cover_dir):
                os.makedirs(cover_dir, mode=0o755, exist_ok=True)
                if not os.path.exists(cover_dir):
                    raise Exception(f"视频封面目录创建失败，路径: {cover_dir}")
                logger.info(f"创建视频封面目录成功: {cover_dir}")
        except Exception as e:
            logger.error(f"创建视频封面目录失败: {str(e)}", {
                "task_id": task_id,
                "output_path": cover_dir,
                "error": str(e)
            })
            raise

        # 最终验证
        if not os.path.exists(upload_dir):
            raise Exception(f"上传目录不存在: {upload_dir}")
        if not os.path.exists(output_path):
            raise Exception(f"输出目录不存在: {output_path}")
        if not os.path.exists(mute_video_path):
            raise Exception(f"静音视频目录不存在: {mute_video_path}")
        if not os.path.exists(un_mute_video_path):
            raise Exception(f"非静音视频目录不存在: {un_mute_video_path}")
        if not os.path.exists(cover_dir):
            raise Exception(f"视频封面目录不存在: {cover_dir}")

        # 检查目录权限
        if not os.access(upload_dir, os.W_OK):
            raise Exception(f"上传目录没有写入权限: {upload_dir}")
        if not os.access(output_path, os.W_OK):
            raise Exception(f"输出目录没有写入权限: {output_path}")
        if not os.access(mute_video_path, os.W_OK):
            raise Exception(f"静音视频目录没有写入权限: {mute_video_path}")
        if not os.access(un_mute_video_path, os.W_OK):
            raise Exception(f"非静音视频目录没有写入权限: {un_mute_video_path}")
        if not os.access(cover_dir, os.W_OK):
            raise Exception(f"视频封面目录没有写入权限: {cover_dir}")

        logger.info("目录创建完成", {
            "task_id": task_id,
            "upload_dir": upload_dir,
            "output_path": output_path,
            "mute_video_path":mute_video_path,
            "un_mute_video_path":un_mute_video_path,
            "cover_dir":cover_dir
        })

        return upload_dir, output_path

    except Exception as e:
        error_msg = f"目录准备失败: {str(e)}"
        logger.error(error_msg, {
            "task_id": task_id,
            "upload_dir": upload_dir if 'upload_dir' in locals() else None,
            "output_path": output_path if 'output_path' in locals() else None,
            "mute_video_path": mute_video_path if 'mute_video_path' in locals() else None,
            "un_mute_video_path": un_mute_video_path if 'un_mute_video_path' in locals() else None,
        })
        raise Exception(error_msg)

# 删除每一次任务的目录
async def cleanup_directories(task_id: str, upload_dir: str, output_path: str):
    """清理任务相关目录

    Args:
        task_id (str): 任务ID
        upload_dir (str): 上传目录路径
        output_path (str): 输出目录路径
    """
    try:
        # 删除上传目录
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)
            logger.info(f"已删除上传目录", {"task_id": task_id, "path": upload_dir})

        # 删除输出目录 
        if os.path.exists(output_path):
            shutil.rmtree(output_path)
            logger.info(f"已删除输出目录", {"task_id": task_id, "path": output_path})

    except Exception as e:
        logger.error("清理目录失败", {
            "task_id": task_id,
            "error": str(e),
            "upload_dir": upload_dir,
            "output_path": output_path
        })

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
        
        api_url = f"http://127.0.0.1:{settings.SCENE_DETECTION_API_PORT}/api/v1/scene-detection/process"
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "input_path": video_path,
                "output_path": output_path,
                "task_id": task_id,
                "video_split_audio_mode": video_split_audio_mode
            }
                
            async with session.post(api_url, json=payload) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if response_data.get("status") == "success" and isinstance(response_data.get("data"), list):
                        scenes = response_data["data"]
                        logger.info(
                            f"{video_split_audio_mode} - 场景分割完成",
                            {"task_id": task_id, "scenes_count": len(scenes)},
                        )
                    else:
                        raise Exception(f"{video_split_audio_mode} - 场景分割API返回格式错误: {response_data}")
                else:
                    error_msg = await response.text()
                    raise Exception(f"{video_split_audio_mode} - 场景分割API请求失败: {error_msg}")

        # 按开始帧排序
        scenes.sort(key=lambda x: x["start_frame"])
        logger.info(
            "场景分割全部完成", {"task_id": task_id, "total_scenes_count": len(scenes)}
        )
        return scenes

    except Exception as e:
        error_msg = str(e)
        await update_task_step(task_id, "scene_cut", "failed", error=error_msg)
        logger.error(f"{video_split_audio_mode} - 场景分割失败", {"task_id": task_id, "error": error_msg})
        raise Exception(f"{video_split_audio_mode} - 场景分割失败: {str(e)}")


async def handle_audio_separation(
    task_id: str, video_path: str, output_path: str
) -> dict:
    """处理音频分离任务

    Args:
        task_id (str): 任务ID
        video_path (str): 视频文件路径
        output_path (str): 输出目录路径

    Returns:
        dict: 包含以下字段的字典:
            - has_audio_stream (bool): 是否包含音频流
            - vocals_path (str): 人声音频文件路径，如果没有音频流则为空字符串

    Raises:
        Exception: 音频分离失败时抛出异常
    """
    try:
        logger.info("开始音频分离", {"task_id": task_id})
        await update_task_step(task_id, "audio_extract", "processing")
        
        api_url = f"http://127.0.0.1:{settings.AUDIO_SEPARATION_API_PORT}/api/v1/audio-separation/process"
        
        payload = {
            "audio_path": video_path,
            "model": "11",  # 使用默认模型
            "task_id": task_id,
            "output_path": output_path
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("status") != "success":
                        raise Exception("API 返回状态不是 success")
                    
                    # 从 file_paths 中获取 vocals 路径
                    file_paths = result.get("file_paths", {})
                    vocals_path = file_paths.get("vocals", "")
                    
                    # 检查是否有音频流
                    has_audio_stream = True
                    if "has_audio_stream" in result:
                        has_audio_stream = result.get("has_audio_stream")
                    
                    if has_audio_stream and not vocals_path:
                        raise Exception("API返回结果中未找到 vocals 文件路径")
                    
                    # 如果有音频流，则更新任务状态为成功
                    if has_audio_stream:
                        await update_task_step(task_id, "audio_extract", "success", vocals_path)
                        logger.info("音频分离完成", {"task_id": task_id, "audio_path": vocals_path})
                    else:
                        await update_task_step(task_id, "audio_extract", "success", "无音频流")
                        logger.info("视频不包含音频流", {"task_id": task_id})
                    
                    return {
                        "has_audio_stream": has_audio_stream,
                        "vocals_path": vocals_path
                    }
                else:
                    error_msg = await response.text()
                    raise Exception(f"音频分离API请求失败: {error_msg}")

    except asyncio.TimeoutError:
        error_msg = "音频分离请求超时"
        await update_task_step(task_id, "audio_extract", "failed", error=error_msg)
        logger.error("音频分离超时", {"task_id": task_id, "error": error_msg})
        raise

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
        
        api_url = f"http://127.0.0.1:{settings.AUDIO_TRANSCRIPTION_API_PORT}/api/v1/audio-transcription/process"
        
        payload = {
            "audio_path": video_path,
            "output_path": output_path,
            "task_id": task_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"语音转写结果{result}")
                    transcription = result.get("transcription", "")  # 获取转写结果
                    
                    await update_task_step(task_id, "text_convert", "success", transcription)
                    logger.info("语音转写完成", {"task_id": task_id})
                    return transcription
                else:
                    error_msg = await response.text()
                    raise Exception(f"语音转写API请求失败: {error_msg}")

    except asyncio.TimeoutError:
        error_msg = "语音转写请求超时"
        await update_task_step(task_id, "text_convert", "failed", error=error_msg)
        logger.error("语音转写超时", {"task_id": task_id, "error": error_msg})
        raise

    except Exception as e:
        error_msg = str(e)
        await update_task_step(task_id, "text_convert", "failed", error=error_msg)
        logger.error

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
        # 获取源文件扩展名
        ext = os.path.splitext(audio_path)[1]  # 包含 `.` 例如 `.mp3`
        # 生成 object_key
        audio_object_key = f"{base_path}/audio{ext}"

        tos_client.upload_file(
            local_file_path=audio_path,
            object_key=audio_object_key,
            metadata={"uid": uid, "task_id": task_id},
        )
        await update_task_step(task_id, "audio_object_key", "success", audio_object_key)

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
        await update_task_step(task_id, "transcription_object_key", "success", transcription_object_key)
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
                # 从 1 开始计数
                scene_object_key = f"{base_path}/{scene_type}/{i + 1}.mp4"
                tos_client.upload_file(
                    local_file_path=scene_path,
                    object_key=scene_object_key,
                    metadata={"uid": uid, "task_id": task_id, "scene_index": i + 1}, # 元数据中的索引也更新
                )
                scene_files.append(
                    {
                        "key": scene_object_key
                    }
                )

        return scene_files
    except Exception as e:
        logger.error("场景文件上传失败", {"task_id": task_id, "error": str(e)})
        raise

async def upload_cover_files(
    cover_list: list, base_path: str, uid: str, task_id: str
) -> list:
    """上传视频封面到对象存储

    Raises:
        Exception: 上传失败时抛出异常
    """
    try:
        tos_client = TOSClient()
        cover_files = []

        for i, cover in enumerate(cover_list):
            cover_path = cover.get("cover")

            if cover_path and os.path.exists(cover_path):
                # 从 1 开始计数
                cover_object_key = f"{base_path}/cover/{i + 1}.jpg"
                tos_client.upload_file(
                    local_file_path=cover_path,
                    object_key=cover_object_key,
                    metadata={"uid": uid, "task_id": task_id, "cover_index": i + 1}, # 元数据中的索引也更新
                )
                cover_files.append(
                    {
                        "key": cover_object_key,
                        "meta_data": cover.get("meta_data")
                    }
                )

        return cover_files
    except Exception as e:
        logger.error("视频片段封面上传失败", {"task_id": task_id, "error": str(e)})
        raise

@celery_app.task(bind=True, name='app.tasks.process_video')
def process_video(self, task_id: str, video_url: str, uid: str, video_split_audio_mode: str):
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

    # 获取当前任务的队列信息
    current_queue = self.request.delivery_info.get('routing_key', 'unknown')
    logger.info(f"任务 {task_id} 正在 {current_queue} 队列中执行")

    async def _process():
        try:
            logger.info("开始处理视频任务", {
                "task_id": task_id,
                "video_url": video_url,
                "uid": uid
            })

            # 1. 更新任务状态为处理中
            await update_task_status_and_log(task_id, TaskStatus.PROCESSING)

            # 2. 准备目录结构
            # 2.1 远程视频下载目录: /data/uploads
            # 2.2 视频解析服务保存目录: /data/processed
            upload_dir, output_path = await prepare_directories(task_id)
            # 当前时间
            now = datetime.now()

            # 3. 下载视频文件
            video_path = os.path.join(upload_dir, "origin")
            logger.info("开始下载视频", {"task_id": task_id, "video_url": video_url})
            video_path = await download_video(video_url, video_path)
            logger.info("视频下载完成", {"task_id": task_id, "video_path": video_path})

            # 4. 拆解视频
            await update_task_step(task_id, "scene_cut", "processing")
            # 4.1 拆解非静音视频
            un_mute_scenes = await handle_scene_detection(
                task_id, video_path, os.path.join(output_path, "un_mute"), AudioMode.UNMUTE
            )
            # 4.1.1 视频文件 tos 地址
            base_path = f"videos/{now.year}/{now.month:02d}/{task_id}"
            # 4.1.2 上传 tos
            un_mute_tos_file = await upload_scene_files(un_mute_scenes, base_path, uid, task_id)
            # 4.1.3 将视频片段的 tos 地址保存到数据库中
            await update_task_step(task_id, "un_mute_scene_files", "success", un_mute_tos_file)

            # 4.2 拆解静音视频
            mute_scenes = await handle_scene_detection(
                task_id, video_path, os.path.join(output_path, "mute"), AudioMode.MUTE
            )
            # 4.2.2 上传 tos
            mute_tos_file = await upload_scene_files(mute_scenes, base_path, uid, task_id)
            # 4.2.3 将视频片段的 tos 地址保存到数据库中
            await update_task_step(task_id, "mute_scene_files", "success", mute_tos_file)

            await update_task_step(task_id, "scene_cut", "success")

            # 5. 人声分离
            audio_info = await handle_audio_separation(task_id, video_path, output_path)
            
            # 5.1.1视频封面文件 tos 地址
            cover_base_path = f"cover/{now.year}/{now.month:02d}/{task_id}"
            
            # 检查是否有音频流
            if audio_info["has_audio_stream"]:
                audio_path = audio_info["vocals_path"]
                
                # 处理音频转写
                transcription = await handle_audio_transcription(
                    task_id, audio_path, output_path
                )
                
                # 5.1
                # 音频文件 tos 地址
                audio_base_path = f"audios/{now.year}/{now.month:02d}/{task_id}"
                
                # 5-1.2 上传音频文件
                await upload_audio_file(audio_path, audio_base_path, uid, task_id)
                
                # 5-2. 上传转写文件
                # 转写文件保存在音频的 tos 目录下
                await upload_transcription_file(
                    transcription, output_path, audio_base_path, uid, task_id
                )
            else:
                # 没有音频流，跳过音频处理步骤
                logger.info("视频没有音频流，跳过音频处理步骤", {"task_id": task_id})
                # 更新任务状态
                await update_task_step(task_id, "text_convert", "success", "无音频流")
            
            # 5-3. 上传场景切割文件
            # 上传视频封面到 tos
            cover_files = await upload_cover_files(un_mute_scenes, cover_base_path, uid, task_id)
            # 将视频封面的 tos 地址保存到数据库中
            await update_task_step(task_id, "cover_list", "success", cover_files)

            # 6. 更新任务状态为完成
            await update_task_status_and_log(task_id, TaskStatus.COMPLETED)
            logger.info("视频处理完成", {"task_id": task_id})

        except Exception as e:
            error_msg = str(e)
            logger.error("视频处理失败", {
                "task_id": task_id,
                "error": error_msg
            })
            # 更新任务状态为失败，并记录错误信息到数据库
            await update_task_status_and_log(task_id, TaskStatus.FAILED, error_msg)
            
            # 尝试记录详细的错误堆栈信息
            try:
                import traceback
                error_traceback = traceback.format_exc()
                
                # 更新数据库中的错误信息，包含更详细的错误内容
                tasks_db.update_task_status(
                    task_id, 
                    TaskStatus.FAILED, 
                    f"{error_msg}\n\n详细错误: {error_traceback[:500]}"  # 限制长度，避免过长
                )
            except Exception as trace_error:
                logger.error("记录错误堆栈信息失败", {
                    "task_id": task_id,
                    "error": str(trace_error)
                })
            
            raise
        finally:
            # 无论任务成功还是失败，都清理目录
            await cleanup_directories(task_id, upload_dir, output_path)

    return asyncio.run(_process())
