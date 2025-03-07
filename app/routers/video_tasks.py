from app.utils.celery_check import check_celery_connection
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, constr, validator
from typing import Optional, Dict, Any
from enum import Enum
import uuid
import httpx
import os
import aiofiles
import re
import traceback
import sys

from app.config import settings
from app.utils.logger import Logger
from app.services.mysql.video_tasks_db import VideoTasksDB
from app.tasks import process_video
from app.utils.tos_client import TOSClient

router = APIRouter()
logger = Logger("video_tasks")

# 初始化数据库连接
tasks_db = VideoTasksDB()


class TaskStatus(str, Enum):
    """任务状态枚举类

    用于表示视频处理任务的不同状态
    """
    SUCCESS = "success"
    PENDING = "pending"  # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 处理完成
    FAILED = "failed"  # 处理失败


class AudioMode(str, Enum):
    """音频处理模式枚举类

    用于表示视频处理时的音频模式
    """

    BOTH = "both"  # 全部模式
    MUTE = "mute"  # 静音模式
    UNMUTE = "un-mute"  # 非静音模式


class CreateTaskRequest(BaseModel):
    """创建任务请求模型

    用于接收创建视频处理任务的请求参数
    """

    video_url: str  # 视频URL地址
    uid: constr(min_length=1, max_length=64)  # 用户ID，限制长度1-64
    video_split_audio_mode: AudioMode = AudioMode.BOTH  # 音频处理模式，默认为全部模式

    @validator("video_url")
    def validate_video_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("视频URL必须以http://或https://开头")
        return v


class TaskResponse(BaseModel):
    """任务响应模型

    用于返回任务处理的状态和结果
    """

    task_id: str  # 任务ID
    status: TaskStatus  # 任务状态
    video_url: str  # 视频URL
    uid: str  # 用户ID
    result: Optional[Dict[str, Any]] = None  # 处理结果
    error: Optional[str] = None  # 错误信息


async def validate_video_size_and_type(video_url: str, task_id: str) -> None:
    """验证视频文件大小和类型

    Args:
        video_url (str): 视频文件的URL地址
        task_id (str): 任务ID

    Raises:
        HTTPException: 当视频大小超过限制或类型不合法时抛出400错误
    """
    logger.info("开始验证视频大小和类型", {"video_url": video_url, "task_id": task_id})
    # 从配置文件读取允许的视频MIME类型
    ALLOWED_VIDEO_TYPES = settings.ALLOWED_VIDEO_TYPES

    try:
        async with httpx.AsyncClient() as client:
            response = await client.head(video_url)
            content_length = int(response.headers.get("content-length", 0))
            content_type = response.headers.get("content-type", "").lower()

            # 验证文件大小
            if content_length > settings.MAX_VIDEO_SIZE:
                logger.warning(
                    "视频文件大小超过限制",
                    {
                        "content_length": content_length,
                        "max_size": settings.MAX_VIDEO_SIZE,
                        "task_id": task_id,
                    },
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"视频文件大小超过限制：{content_length} > {settings.MAX_VIDEO_SIZE} 字节",
                )

            # 验证文件类型
            if not any(
                video_type in content_type for video_type in ALLOWED_VIDEO_TYPES
            ):
                logger.warning(
                    "不支持的视频文件类型",
                    {"content_type": content_type, "task_id": task_id},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的视频文件类型,支持的类型：MP4, AVI, MOV, MKV, WebM",
                )

            logger.info(
                "视频验证通过",
                {
                    "task_id": task_id,
                    "content_length": content_length,
                    "content_type": content_type,
                },
            )
    except httpx.RequestError as e:
        logger.error("视频URL访问失败", {"task_id": task_id, "error": str(e)})
        raise HTTPException(status_code=400, detail="视频URL访问失败")


@router.post("/create", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest):
    """创建视频处理任务

    Args:
        request (CreateTaskRequest): 包含视频URL和用户ID的请求对象

    Returns:
        TaskResponse: 包含任务ID和初始状态的响应对象

    Raises:
        HTTPException: 当任务创建失败时抛出相应的错误
    """

    # 首先检查连接
    if not check_celery_connection():
        raise HTTPException(
            status_code=503,
            detail="任务处理服务暂时不可用，请稍后重试"
        )


    # 创建taskid
    task_id = str(uuid.uuid4())
    logger.log_request(
        "POST",
        "/api/v1/video-tasks/create",
        {"task_id": task_id, "video_url": request.video_url, "uid": request.uid},
    )

    try:
        # 验证视频大小和类型
        await validate_video_size_and_type(request.video_url, task_id)


        # 创建任务记录
        if not tasks_db.create_task(task_id, request.video_url, request.uid):
            logger.error("创建任务失败", {"task_id": task_id})
            # 更新任务状态为失败
            tasks_db.update_task_status(task_id, TaskStatus.FAILED, "任务创建失败")
            raise HTTPException(status_code=500, detail="任务创建失败, 请稍后重试")

        logger.log_task_status(task_id, TaskStatus.PENDING)


        # 构建返回数据
        task = {
            "task_id": task_id,
            "status": TaskStatus.SUCCESS,
            "video_url": request.video_url,
            "uid": request.uid,
            "result": None,
            "error": None,
        }

        # 启动异步任务
        process_video.apply_async(
            kwargs={
                'task_id': task_id,
                'video_url': request.video_url,
                'uid': request.uid,
                'video_split_audio_mode': request.video_split_audio_mode
            }
        )

        logger.log_response(200, "/api/v1/video-tasks/create", {"task_id": task_id})
        return TaskResponse(**task)

    except HTTPException as he:
        # 处理 HTTP 异常
        if task_id:
            tasks_db.update_task_status(task_id, TaskStatus.FAILED, str(he.detail))
            logger.log_task_status(task_id, TaskStatus.FAILED)
        logger.error("HTTP异常", {"task_id": task_id, "error": str(he.detail)})
        raise

    except Exception as e:
        # 获取异常的详细信息
        exc_type, exc_value, exc_traceback = sys.exc_info()
        # 获取堆栈跟踪信息
        stack_trace = traceback.extract_tb(exc_traceback)
        # 获取最后一个堆栈帧（异常发生的位置）
        last_frame = stack_trace[-1]
        error_location = f"{last_frame.filename}:{last_frame.lineno}"

        error_detail = {
            "task_id": task_id,
            "error_type": exc_type.__name__,
            "error_message": str(e),
            "error_location": error_location,
            "stack_trace": traceback.format_exc()
        }
        # 处理其他异常
        if task_id:
            tasks_db.update_task_status(task_id, TaskStatus.FAILED, str(e))
            logger.log_task_status(task_id, TaskStatus.FAILED)
        logger.error("创建任务失败", {"task_id": task_id, "error": error_detail})
        raise HTTPException(
            status_code=500,
            detail=f"服务器内部错误 (位置: {error_location})"
        )


@router.get("/get/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取任务状态和结果

    Args:
        task_id (str): 任务ID

    Returns:
        TaskResponse: 包含任务状态和结果的响应对象

    Raises:
        HTTPException: 当任务不存在或ID格式不正确时抛出相应错误
    """
    # 验证task_id格式
    if not re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        task_id,
    ):
        raise HTTPException(status_code=400, detail="无效的任务ID格式")

    task = tasks_db.get_task(task_id)
    formatted_result = format_task_result(task)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskResponse(**formatted_result)


@router.post("/upload_test", response_model=TaskResponse)
async def upload_video(file: UploadFile = File(...), uid: str = None):
    """上传视频文件

    Args:
        file (UploadFile): 上传的视频文件
        uid (str, optional): 用户ID

    Returns:
        TaskResponse: 上传到tos上的视频文件信息

    Raises:
        HTTPException: 当文件上传失败或格式不正确时抛出相应的错误
    """
    # 创建任务ID
    task_id = str(uuid.uuid4())
    logger.log_request(
        "POST",
        "/api/v1/video-tasks/upload",
        {"task_id": task_id, "filename": file.filename, "uid": uid},
    )

    try:
        # 验证文件大小
        content = await file.read()
        file_size = len(content)
        if file_size > settings.MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"视频文件大小超过限制：{file_size} > {settings.MAX_VIDEO_SIZE} 字节",
            )

        # 保存文件到临时目录
        video_path = f"data/download/{task_id}.mp4"
        async with aiofiles.open(video_path, "wb") as out_file:
            await out_file.write(content)

        # 上传文件到TOS
        tos_client = TOSClient()
        object_key = f"videos/{task_id}/{file.filename}"
        upload_result = tos_client.upload_file(
            local_file_path=video_path,
            object_key=object_key,
            metadata={"uid": uid} if uid else None,
        )

        # 构建返回数据
        task = {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "video_url": upload_result.get("object_key", ""),  # 使用上传后的对象路径
            "uid": uid or "anonymous",
            "result": upload_result,  # 直接使用上传结果
            "error": None,
        }

        logger.log_response(200, "/api/v1/video-tasks/upload", {"task_id": task_id})
        return TaskResponse(**task)

    except Exception as e:
        # 清理临时文件
        video_path = f"data/download/{task_id}.mp4"
        if os.path.exists(video_path):
            os.remove(video_path)
        logger.error("上传视频失败", {"task_id": task_id, "error": str(e)})
        raise

def format_task_result(task: dict) -> dict:
    """格式化任务结果数据

    Args:
        task: 原始任务数据

    Returns:
        dict: 格式化后的数据结构
    """

    # 检查 task 是否为字典类型
    if not isinstance(task, dict):
        raise HTTPException(
            status_code=500, 
            detail=f"任务数据格式错误: 预期 dict 类型，实际为 {type(task)}"
        )
    
    # 检查 task 是否存在
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查必需字段
    required_fields = ["task_id", "status", "video_url", "uid"]
    missing_fields = [field for field in required_fields if field not in task]
    if missing_fields:
        raise HTTPException(
            status_code=500,
            detail=f"任务数据缺失必需字段: {', '.join(missing_fields)}"
        )

    # 如果任务未完成，只返回基本信息
    if task["status"] == TaskStatus.FAILED:
        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "video_url": task["video_url"],
            "uid": task["uid"],
            "error":"error"
        }
    
    # 检查 result 字段是否为字典类型
    if not isinstance(task.get("result"), dict):
        raise HTTPException(
            status_code=500,
            detail="任务结果格式错误: result 字段必须为字典类型"
        )

    formatted_result = {
        "task_id": task["task_id"],
        "status": task["status"],
        "video_url": task["video_url"],
        "uid": task["uid"],
        "result": {
            "video_list": [],
            "audio_url": "",
            "audio_text": ""
        }
    }
    
    task_result = task["result"]
    
    # 获取音频文本和音频URL
    if task_result.get("text_convert", {}).get("status") == "success":
        formatted_result["result"]["audio_text"] = task_result["text_convert"]["output"]
    
    if task_result.get("audio_object_key", {}).get("status") == "success":
        formatted_result["result"]["audio_url"] = task_result["audio_object_key"]["output"]
    
    # 获取封面列表
    cover_list = task_result.get("cover_list", {}).get("output", [])
    cover_dict = {str(i+1): item for i, item in enumerate(cover_list)}
    
    # 获取静音和非静音视频
    mute_videos = {
        video.get("key", "").split("/")[-1].split(".")[0]: video
        for video in task_result.get("mute_scene_files", {}).get("output", [])
    }
    
    unmute_videos = {
        video.get("key", "").split("/")[-1].split(".")[0]: video
        for video in task_result.get("un_mute_scene_files", {}).get("output", [])
    }
    
    # 合并视频列表
    all_indexes = sorted(set(mute_videos.keys()) | set(unmute_videos.keys()))
    for index in all_indexes:
        mute_video = mute_videos.get(index, {})
        unmute_video = unmute_videos.get(index, {})
        cover_info = cover_dict.get(index, {})
        
        video_pair = {
            "mute_video_url": mute_video.get("key", ""),
            "un_mute_video_url": unmute_video.get("key", ""),
            "cover_url": cover_info.get("key", ""),
            "meta_data": cover_info.get("meta_data", {})
        }
        formatted_result["result"]["video_list"].append(video_pair)
    
    return formatted_result