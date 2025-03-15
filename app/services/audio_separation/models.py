from pydantic import BaseModel
from typing import Dict, Optional

# 定义响应结构体
class SeparationResponse(BaseModel):
    # 状态
    status: str
    # 任务ID
    task_id: str
    # 消息
    message: Optional[str] = None
    # 是否包含音频流
    has_audio_stream: bool = True
    # 分离后的音频
    separated_audio: Dict[str, str]
    # 音频路径
    file_paths: Dict[str, str]

# 定义请求结构体
class SeparationRequest(BaseModel):
    # 音频路径
    audio_path: str
    # 模型
    model: str
    # 任务ID
    task_id: str
    # 输出路径
    output_path: str

