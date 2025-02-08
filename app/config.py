from pydantic import BaseSettings
from typing import Optional, Set
from pathlib import Path


class Settings(BaseSettings):
    """应用程序配置类

    用于管理应用程序的所有配置项，包括基础设置、文件存储、音视频处理参数等。
    继承自pydantic.BaseSettings，支持从环境变量和.env文件加载配置。
    """

    # 基础配置
    APP_NAME: str  # 应用程序名称
    API_V1_STR: str  # API版本前缀
    DEBUG: bool  # 调试模式开关

    # 文件存储路径配置
    DATA_DIR: str  # 数据根目录
    UPLOAD_DIR: str  # 上传文件存储目录
    PROCESSED_DIR: str  # 处理后文件存储目录

    # 音频处理配置
    MAX_AUDIO_SIZE: int  # 最大音频文件大小（字节）
    ALLOWED_AUDIO_TYPES: Set[str]  # 允许的音频文件类型集合

    # 视频处理配置
    MAX_VIDEO_SIZE: int  # 最大视频文件大小（字节）
    ALLOWED_VIDEO_TYPES: Set[str]  # 允许的视频文件类型集合

    # 子任务超时配置（单位：秒）
    SCENE_DETECTION_TIMEOUT: int  # 场景检测任务超时时间
    AUDIO_SEPARATION_TIMEOUT: int  # 音频分离任务超时时间
    AUDIO_TRANSCRIPTION_TIMEOUT: int  # 音频转写任务超时时间

    # 子任务API服务配置
    SCENE_DETECTION_API_PORT: int  # 场景检测服务端口
    AUDIO_SEPARATION_API_PORT: int  # 音频分离服务端口
    AUDIO_TRANSCRIPTION_API_PORT: int  # 音频转写服务端口

    class Config:
        """配置类设置

        case_sensitive: 区分大小写
        env_file: 环境变量文件路径
        """

        case_sensitive = True
        env_file = ".env"


settings = Settings()  # 创建全局配置实例
