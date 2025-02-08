from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum
import uuid
import httpx
import os
from app.config import settings
from app.utils.logger import Logger
from fastapi import UploadFile, File
import aiofiles
import shutil

router = APIRouter()
logger = Logger("video_tasks")

from app.services.mysql.video_tasks_db import VideoTasksDB

# 初始化数据库连接
tasks_db = VideoTasksDB()


class TaskStatus(str, Enum):
    """任务状态枚举类

    用于表示视频处理任务的不同状态
    """

    PENDING = "pending"  # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 处理完成
    FAILED = "failed"  # 处理失败


class CreateTaskRequest(BaseModel):
    """创建任务请求模型

    用于接收创建视频处理任务的请求参数
    """

    video_url: str  # 视频URL地址
    uid: str  # 用户ID


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


async def download_and_validate_video(video_url: str, task_id: str) -> str:
    """下载并验证视频文件

    Args:
        video_url (str): 视频文件的URL地址
        task_id (str): 任务ID

    Returns:
        str: 下载后的视频文件本地路径

    Raises:
        HTTPException: 当视频大小超过限制时抛出400错误
    """
    logger.info("开始下载视频", {"video_url": video_url, "task_id": task_id})
    # 检查视频大小
    async with httpx.AsyncClient() as client:
        response = await client.head(video_url)
        content_length = int(response.headers.get("content-length", 0))

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

        # 下载视频
        response = await client.get(video_url)
        video_path = f"data/download/{task_id}.mp4"
        with open(video_path, "wb") as f:
            f.write(response.content)

        logger.info("视频下载完成", {"task_id": task_id, "video_path": video_path})
        return video_path


@router.post("/api/v1/video-handle/create", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest):
    """创建视频处理任务

    Args:
        request (CreateTaskRequest): 包含视频URL和用户ID的请求对象

    Returns:
        TaskResponse: 包含任务ID和初始状态的响应对象

    Raises:
        HTTPException: 当任务创建失败时抛出相应的错误
    """
    # 创建taskid
    task_id = str(uuid.uuid4())
    logger.log_request(
        "POST",
        "/api/v1/video-handle/create",
        {"task_id": task_id, "video_url": request.video_url, "uid": request.uid},
    )

    try:
        # 下载并验证视频
        video_path = await download_and_validate_video(request.video_url, task_id)

        # 创建任务记录
        if not tasks_db.create_task(task_id, request.video_url, request.uid):
            raise HTTPException(
                status_code=500, detail="Failed to create task in database"
            )
        logger.log_task_status(task_id, TaskStatus.PENDING)

        # 构建返回数据
        task = {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "video_url": request.video_url,
            "uid": request.uid,
            "result": None,
            "error": None,
        }

        # 启动异步任务
        from app.tasks import process_video

        process_video.delay(task_id, video_path, request.uid)

        logger.log_response(200, "/api/v1/video-handle/create", {"task_id": task_id})
        return TaskResponse(**task)

    except Exception as e:
        # 如果发生错误，确保清理已下载的文件
        video_path = f"data/download/{task_id}.mp4"
        if os.path.exists(video_path):
            os.remove(video_path)
        logger.error("创建任务失败", {"task_id": task_id, "error": str(e)})
        raise


@router.get("/api/v1/video-handle/get/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取任务状态和结果

    Args:
        task_id (str): 任务ID

    Returns:
        TaskResponse: 包含任务状态和结果的响应对象

    Raises:
        HTTPException: 当任务不存在时抛出404错误
    """
    task = tasks_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**task)


@router.post("/api/v1/video-handle/upload", response_model=TaskResponse)
async def upload_video(file: UploadFile = File(...), uid: str = None):
    """上传视频文件

    Args:
        file (UploadFile): 上传的视频文件
        uid (str, optional): 用户ID

    Returns:
        TaskResponse: 包含任务ID和初始状态的响应对象

    Raises:
        HTTPException: 当文件上传失败或格式不正确时抛出相应的错误
    """
    if not uid:
        raise HTTPException(status_code=400, detail="用户ID不能为空")

    # 验证文件类型
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="只支持上传视频文件")

    # 创建任务ID
    task_id = str(uuid.uuid4())
    logger.log_request(
        "POST",
        "/api/v1/video-handle/upload",
        {"task_id": task_id, "filename": file.filename, "uid": uid},
    )

    try:
        # 读取文件内容到内存以检查大小
        content = await file.read()
        if len(content) > settings.MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"视频文件大小超过限制：{len(content)} > {settings.MAX_VIDEO_SIZE} 字节",
            )

        # 保存文件
        video_path = f"data/download/{task_id}.mp4"
        async with aiofiles.open(video_path, "wb") as out_file:
            await out_file.write(content)

        # 创建任务记录
        if not tasks_db.create_task(task_id, video_path, uid):
            raise HTTPException(
                status_code=500, detail="Failed to create task in database"
            )
        logger.log_task_status(task_id, TaskStatus.PENDING)

        # 构建返回数据
        task = {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "video_url": video_path,
            "uid": uid,
            "result": None,
            "error": None,
        }

        # 启动异步任务
        from app.tasks import process_video

        process_video.delay(task_id, video_path, uid)

        logger.log_response(200, "/api/v1/video-handle/upload", {"task_id": task_id})
        return TaskResponse(**task)

    except Exception as e:
        # 如果发生错误，确保清理已上传的文件
        video_path = f"data/download/{task_id}.mp4"
        if os.path.exists(video_path):
            os.remove(video_path)
        logger.error("文件上传失败", {"task_id": task_id, "error": str(e)})
        raise
