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
- Redis（缓存和消息队列）
- MySQL（数据存储）

## 服务架构

项目采用微服务架构，主要包含以下服务：

- **MySQL服务**：负责数据持久化存储
- **Redis服务**：提供缓存和消息队列功能
- **视频场景分割服务**：基于TransNetV2的视频分割处理
- **音频分离服务**：处理音频分离任务
- **语音转写服务**：提供语音识别转写功能

## 环境配置

### 环境变量配置（.env）

```bash
# MySQL配置
MYSQL_HOST=localhost        # MySQL主机地址
MYSQL_PORT=3306            # MySQL端口
MYSQL_DATABASE=media_symphony  # 数据库名称
MYSQL_USER=media_symphony   # 数据库用户名
MYSQL_PASSWORD=your_password  # 数据库密码
MYSQL_ROOT_PASSWORD=root_password  # Root密码

# Redis配置
REDIS_HOST=localhost        # Redis主机地址
REDIS_PORT=6379            # Redis端口
REDIS_PASSWORD=your_password  # Redis密码
```

### 服务配置

1. **Redis配置**
   - 持久化：启用AOF和RDB双重持久化
   - 内存管理：最大内存1GB，使用LRU淘汰策略
   - 连接限制：最大连接数10000
   - 安全设置：禁用危险命令，启用密码认证

2. **MySQL配置**
   - 字符集：utf8mb4
   - 连接数：最大连接数1000
   - 缓存设置：InnoDB缓冲池大小等根据服务器配置调整

## 部署说明

1. 克隆项目
```bash
git clone https://github.com/duanfuxing/MediaSymphony.git
cd MediaSymphony
```

2. 配置环境变量
```bash
cp .env.example .env  # 复制环境变量模板
# 编辑.env文件，设置相应的配置项
```

3. 使用Docker Compose启动服务
```bash
docker-compose up -d  # 后台启动所有服务
```

4. 验证服务状态
```bash
docker-compose ps     # 查看所有服务状态
```

## API接口文档

### 创建视频处理任务

```http
POST /api/v1/video-handle/create

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
GET /api/v1/video-handle/get

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
- 首次启动服务时，需要等待所有容器初始化完成
- 请确保服务器有足够的内存和CPU资源

## 许可证

MIT License