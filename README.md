# MediaSymphony

## 项目介绍
MediaSymphony是一个强大的媒体处理平台，提供视频场景分割、音频分离和语音转写等功能。该平台采用微服务架构，使用FastAPI和Celery构建，能够高效处理大规模的媒体文件。

## 系统架构

### 系统交互流程
```
用户 → [主API] → Redis任务队列
                ↓
           Celery Workers（heavy_tasks队列）
                ↓
      子任务API（场景切割/音频提取/语音转写）
                ↓
          [MySQL状态存储]
                ↓
        [Prometheus + Grafana监控]
```

### 核心组件
- **主应用服务**: 处理HTTP请求，管理任务队列
- **视频场景分割服务**: 分析视频内容，识别场景转换
- **音频分离服务**: 从视频中提取音频并进行分离
- **语音转写服务**: 将音频转换为文本

### 目录结构
```
├── app/
│   ├── main.py            # 应用入口
│   ├── config.py          # 配置文件
│   ├── routers/          # 路由模块
│   │   └── video_tasks.py # 视频处理任务路由
│   ├── services/         # 微服务模块
│   │   ├── audio_separation/    # 音频分离服务
│   │   ├── audio_transcription/ # 语音转写服务
│   │   ├── video_scene_split/   # 视频场景分割服务
│   │   ├── mysql/              # MySQL服务
│   │   └── redis/              # Redis服务
│   └── utils/            # 工具函数
├── data/                 # 数据目录
│   ├── download/         # 下载文件目录
│   └── processed/        # 处理后文件目录
└── requirements.txt      # 依赖配置
```

## 功能特性
1. **视频场景分割**
   - 自动检测视频场景转换点
   - 支持多种视频格式

2. **音频分离**
   - 从视频中提取音频
   - 支持多种音频格式

3. **语音转写**
   - 将音频转换为文本
   - 支持多语言识别

## API文档

### 主服务API
#### 创建视频处理任务
```http
POST /api/v1/video-tasks/create

请求体：
{
    "video_url": "视频URL地址",
    "uid": "用户ID",
    "video_split_audio_mode": "音频处理模式，可选值：both（全部）、mute（静音）、un-mute（非静音），默认为both"
}

响应：
{
    "task_id": "任务ID",
    "status": "pending",
    "video_url": "视频URL",
    "uid": "用户ID",
    "result": null,
    "error": null
}
```

#### 上传视频文件
```http
POST /api/v1/video-tasks/upload

请求体：
- multipart/form-data
- 参数：
  - file: 视频文件
  - uid: 用户ID

响应：
{
    "task_id": "任务ID",
    "status": "pending",
    "video_url": "本地文件路径",
    "uid": "用户ID",
    "result": null,
    "error": null
}
```

#### 获取任务状态
```http
GET /api/v1/video-tasks/get/{task_id}

响应：
{
    "task_id": "任务ID",
    "status": "completed",
    "video_url": "视频URL",
    "uid": "用户ID",
    "result": {
        "scenes": [...],
        "transcription": "..."
    }
}
```

### 子服务API
#### 画面切割API
```http
POST http://localhost:5000/api/v1/scene-detection/process

请求体：
{
    "input_path": "视频文件路径",
    "output_path": "输出目录路径",
    "task_id": "任务ID",
    "video_split_audio_mode":"mute|un-mute|both" # 音频处理模式，可选值：both（全部）、mute（静音）、un-mute（非静音），默认为both
    "threshold": 0.35,  # 场景切换阈值（可选）
    "visualize": false  # 是否生成预测可视化（可选）
}

响应：
{
    "status": "success|error",
    "message":"成功或失败的信息",
    "task_id": "任务ID",
    "output_dir": "处理后视频存放目录路径",
    "data": [
        {
            "start_frame": 0,
            "end_frame": 120,
            "start_time": "00:00:00",
            "end_time": "00:00:05"
        }
    ]
}
```

#### 人声分离API
```http
POST http://localhost:5001/api/v1/audio-separation/process

请求体：
{
    "audio_path": "音频文件路径",
    "model": "vocals",  # 分离模型类型（可选：vocals, drums, bass, other）
    "task_id": "任务ID"  # 用于追踪任务的唯一标识符
}

响应：
{
    "status": "success",
    "task_id": "任务ID",
    "separated_audio": {
        "vocals": "vocals.wav",
        "accompaniment": "accompaniment.wav"
    },
    "file_paths": {
        "vocals": "/path/to/processed/vocals.wav",
        "accompaniment": "/path/to/processed/accompaniment.wav"
    }
}
```

#### 语音转文字API
```http
POST http://localhost:5002/api/v1/audio-transcription/process

请求体：
{
    "audio_path": "音频文件路径",
    "language": "zh-CN",  # 语言代码（可选）
    "model": "medium",  # 模型大小（可选：tiny, base, medium, large）
    "task_id": "任务ID"  # 用于追踪任务的唯一标识符
}

响应：
{
    "status": "success",
    "task_id": "任务ID",
    "transcription": "转写的文本内容",
    "transcription_path": "/path/to/processed/transcription.txt",
    "segments": [
        {
            "start": 0.0,
            "end": 2.5,
            "text": "分段文本内容"
        }
    ]
}
```

## 部署说明

### 环境要求
- Python 3.8+
- Redis
- MySQL
- FFmpeg

### 安装步骤
1. 克隆项目
```bash
git clone https://github.com/yourusername/MediaSymphony.git
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，设置必要的环境变量
```

4. 启动服务
```bash
# 启动主应用
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 启动Celery工作进程
celery -A app.celery_app worker --loglevel=info
```

## 监控和日志
- 使用Prometheus进行指标收集
- 详细的日志记录系统，支持多级别日志
- 任务状态实时跟踪

## 许可证
MIT License