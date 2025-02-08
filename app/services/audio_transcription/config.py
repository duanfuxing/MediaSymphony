import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class Settings:
    # 运行主机
    HOST = os.getenv("HOST", "0.0.0.0")
    # 运行端口,确保端口是整数
    PORT = int(os.getenv("PORT", 6001))
    # 服务读取的模型文件目录
    MODEL_DIR= os.getenv("MODEL_DIR", "./iic/SenseVoiceSmall")
    # cuda 设备,默认使用第一个设备 多设备
    CUDA_DEVICE = os.getenv("CUDA_DEVICE", "cuda:0")

settings = Settings()
