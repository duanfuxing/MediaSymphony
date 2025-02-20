FROM nvidia/cuda:12.6.3-cudnn-devel-ubuntu22.04

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    ffmpeg \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 安装Python依赖
RUN pip3 install --no-cache-dir ffmpeg-python \
    opencv-python \
    numpy \
    flask \
    gunicorn \
    tensorflow \
    pillow \
    tqdm \
    moviepy

# 设置环境变量
ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES compute,video,utility

# 暴露API端口
EXPOSE 5000

# 启动命令
CMD ["python3", "/app/server/api_server.py"]