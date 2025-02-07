from pydantic import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    # 基础配置
    APP_NAME: str = "MediaSymphony"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # 文件存储路径配置
    DATA_DIR: str = str(Path("../data").absolute())
    UPLOAD_DIR: str = str(Path(DATA_DIR) / "uploads")
    PROCESSED_DIR: str = str(Path(DATA_DIR) / "processed")

    # 音频处理配置
    MAX_AUDIO_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_AUDIO_TYPES: set = {"audio/wav", "audio/mp3", "audio/ogg"}

    # 视频处理配置
    MAX_VIDEO_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_VIDEO_TYPES: set = {"video/mp4", "video/avi", "video/mov"}

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
