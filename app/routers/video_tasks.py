from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum
import uuid

router = APIRouter()

# 模拟数据存储
tasks_db: Dict[str, Dict[str, Any]] = {}


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateTaskRequest(BaseModel):
    video_url: str


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    video_url: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/api/v1/video-handle/create", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest):

    # 创建taskid
    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "video_url": request.video_url,
        "result": None,
        "error": None,
    }
    tasks_db[task_id] = task
    return TaskResponse(**task)


@router.get("/api/v1/video-handle/get/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**task)
