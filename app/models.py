from enum import Enum


class TaskStatus(Enum):
    """任务状态枚举类

    用于表示视频处理任务的不同状态
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioMode(str, Enum):
    """音频处理模式枚举类

    用于表示视频处理时的音频模式
    """

    BOTH = "both"  # 全部模式
    MUTE = "mute"  # 静音模式
    UNMUTE = "un-mute"  # 非静音模式
