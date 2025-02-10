import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class Settings:
    # 模型文件存储目录
    MODEL_DIR = os.getenv("MODEL_DIR", "/data/audio-separator-models")
    # 音频分离结果输出目录
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/data/audio-separator-outputs")
    # 临时文件存储目录
    TEMP_DIR = os.getenv("TEMP_DIR", "/data/audio-separator-temp")
    # 模型文件名
    MODEL_FILENAME = os.getenv("MODEL_FILENAME", "UVR-MDX-NET-Inst_HQ_3.onnx")
    # 上传文件大小限制,默认100MB
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))  # 100MB
    # 允许上传的音频文件格式

    ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
    # 静态文件服务URL
    STATIC_SERVE_URL = os.getenv("STATIC_SERVE_URL", "http://101.200.146.208:6002")
    # 服务运行端口,确保端口是整数
    PORT = int(os.getenv("PORT", 6000))

settings = Settings()
