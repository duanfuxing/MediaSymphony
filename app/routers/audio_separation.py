from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from pathlib import Path
import shutil

router = APIRouter()


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    """上传音频文件接口"""
    if file.content_type not in settings.ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail="不支持的音频文件格式")

    # 确保上传目录存在
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 保存文件
    file_path = upload_dir / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"filename": file.filename, "status": "success"}


@router.post("/separate")
async def separate_audio(file_id: str):
    """音频分离处理接口"""
    return {"status": "processing", "file_id": file_id}


@router.get("/status/{task_id}")
async def get_separation_status(task_id: str):
    """获取音频分离任务状态"""
    return {"task_id": task_id, "status": "pending"}
