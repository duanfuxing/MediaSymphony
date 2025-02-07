FROM nvidia/cuda:12.6.3-cudnn-devel-ubuntu22.04

# 定义 UID 和 GID 参数，默认值设为 1000
ARG USER_UID=1000
ARG USER_GID=1000

# 创建非 root 用户
RUN groupadd -r -g ${USER_GID} transnet && \
    useradd -r -u ${USER_UID} -g transnet -m transnet

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    ffmpeg \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制应用文件
COPY --chown=transnet:transnet setup.py /app/
COPY --chown=transnet:transnet inference /app/inference/
COPY --chown=transnet:transnet server /app/server/

# 创建必要的目录并设置权限
RUN mkdir -p /app/server/input /app/server/output \
    && chown -R transnet:transnet /app

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

# 安装TransNetV2
RUN cd /app && python3 setup.py install

# 设置环境变量
ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES compute,video,utility

# 切换到非 root 用户
USER transnet

# 暴露API端口
EXPOSE 5000

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "server.api_server:app"]