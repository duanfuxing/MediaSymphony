# MediaSymphony

MediaSymphony是一个强大的多媒体处理服务平台，提供音频分离、音频转写和视频场景分割等功能。

## 功能特性

- **音频分离**：将混合音频分离成不同的音轨
- **音频转写**：将音频文件转换为文本
- **视频场景分割**：自动检测和分割视频中的场景

## 安装部署

### 环境要求

- Python 3.7+
- FastAPI 0.68.0
- OpenCV 4.5.3+

### 安装步骤

1. 克隆项目
```bash
git clone https://github.com/duanfuxing/MediaSymphony.git
cd MediaSymphony
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 启动服务
```bash
uvicorn app.main:app --reload
```

## API文档

### 音频分离

#### 上传音频文件
```http
POST /api/v1/audio-separation/upload
```

#### 开始音频分离
```http
POST /api/v1/audio-separation/separate
```

#### 查询分离状态
```http
GET /api/v1/audio-separation/status/{task_id}
```

### 音频转写

#### 上传音频文件
```http
POST /api/v1/audio-transcription/upload
```

#### 开始音频转写
```http
POST /api/v1/audio-transcription/transcribe
```

#### 查询转写状态
```http
GET /api/v1/audio-transcription/status/{task_id}
```

#### 获取转写结果
```http
GET /api/v1/audio-transcription/result/{task_id}
```

### 视频场景分割

#### 上传视频文件
```http
POST /api/v1/video-scene-split/upload
```

#### 开始场景分割
```http
POST /api/v1/video-scene-split/split
```

#### 查询分割状态
```http
GET /api/v1/video-scene-split/status/{task_id}
```

#### 获取分割结果
```http
GET /api/v1/video-scene-split/result/{task_id}
```

## 文件格式支持

### 音频格式
- WAV
- MP3
- OGG

### 视频格式
- MP4
- AVI
- MOV

## 目录结构

```
├── app/                    # 应用主目录
│   ├── config.py          # 配置文件
│   ├── main.py            # 主程序入口
│   ├── routers/           # 路由模块
│   └── services/          # 服务模块
├── data/                  # 数据目录
│   ├── uploads/           # 上传文件存储
│   └── processed/         # 处理结果存储
├── log/                   # 日志目录
└── requirements.txt       # 项目依赖
```

## 配置说明

主要配置项（在.env文件中设置）：

```ini
APP_NAME=MediaSymphony
API_V1_STR=/api/v1
DEBUG=True

# 文件大小限制
MAX_AUDIO_SIZE=104857600  # 100MB
MAX_VIDEO_SIZE=524288000  # 500MB
```

## 使用示例

### 音频分离示例

```python
import requests

# 上传音频文件
files = {'file': open('music.mp3', 'rb')}
response = requests.post('http://localhost:8000/api/v1/audio-separation/upload', files=files)
file_id = response.json()['file_id']

# 开始分离处理
response = requests.post('http://localhost:8000/api/v1/audio-separation/separate', json={'file_id': file_id})
task_id = response.json()['task_id']

# 查询处理状态
response = requests.get(f'http://localhost:8000/api/v1/audio-separation/status/{task_id}')
print(response.json())
```

## 许可证

MIT License