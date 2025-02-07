import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class Settings:
    MODEL_DIR = os.getenv("MODEL_DIR", "/tmp/audio-separator-models")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp/audio-separator-outputs")
    TEMP_DIR = os.getenv("TEMP_DIR", "/tmp/audio-separator-temp")
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))  # 100MB
    ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
    STATIC_SERVE_URL = os.getenv("STATIC_SERVE_URL", "http://101.200.146.208:6002")
    PORT = int(os.getenv("PORT", 6000))  # 确保端口是整数

settings = Settings()
