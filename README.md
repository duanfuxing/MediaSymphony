# MediaSymphony

MediaSymphony是一个强大的媒体处理服务，提供视频处理、音频分离和语音转写等功能。

## 功能特点

- 视频场景分割
- 音频分离处理
- 语音转写服务
- 异步任务处理

## 技术栈

- FastAPI
- Python 3.x
- FunASR（语音识别）
- TransnetV2（视频分割）

## 安装部署

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

## API接口文档

### 创建视频处理任务

```http
POST /video-tasks/

Request Body:
{
    "video_url": "string"
}

Response:
{
    "task_id": "string",
    "status": "pending",
    "video_url": "string",
    "result": null,
    "error": null
}
```

### 查询任务状态

```http
GET /video-tasks/{task_id}

Response:
{
    "task_id": "string",
    "status": "pending|processing|completed|failed",
    "video_url": "string",
    "result": object,
    "error": string
}
```

## 项目结构

```
├── app/
│   ├── main.py            # 应用入口
│   ├── config.py          # 配置文件
│   ├── routers/          # 路由模块
│   └── services/         # 服务模块
├── data/                 # 数据目录
└── requirements.txt      # 依赖配置
```

## 注意事项

- 确保有足够的磁盘空间用于存储上传的媒体文件
- 视频处理可能需要较长时间，请通过任务ID查询进度
- 建议在处理大文件时使用异步任务处理

## 许可证

MIT License