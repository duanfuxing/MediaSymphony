from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from pathlib import Path
import shutil
import cv2
import numpy as np

router = APIRouter()


@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """上传视频文件接口"""
    if file.content_type not in settings.ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="不支持的视频文件格式")

    if file.size > settings.MAX_VIDEO_SIZE:
        raise HTTPException(status_code=400, detail="视频文件大小超过限制")

    # 确保上传目录存在
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 保存文件
    file_path = upload_dir / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"filename": file.filename, "status": "success"}


@router.post("/split")
async def split_video_scenes(file_id: str):
    """视频场景分割处理接口"""
    return {"status": "processing", "file_id": file_id}


@router.get("/status/{task_id}")
async def get_split_status(task_id: str):
    """获取场景分割任务状态"""
    return {"task_id": task_id, "status": "pending"}


@router.get("/result/{task_id}")
async def get_split_result(task_id: str):
    """获取场景分割结果"""
    return {"task_id": task_id, "scenes": [], "status": "pending"}
