from enum import Enum
from pydantic import BaseModel, StringConstraints
from typing import Optional, Dict, Any, Annotated

class TaskStatus(str, Enum):
    """任务状态枚举类"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AudioMode(str, Enum):
    """音频处理模式枚举类"""
    BOTH = "both"
    MUTE = "mute"
    UNMUTE = "un-mute"

class CreateTaskRequest(BaseModel):
    """创建任务请求模型"""
    video_url: str
    uid: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    video_split_audio_mode: AudioMode = AudioMode.BOTH

class TaskResponse(BaseModel):
    """任务响应模型"""
    task_id: str
    status: TaskStatus
    video_url: str
    uid: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None 