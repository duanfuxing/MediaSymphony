from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import video_tasks

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,  # 设置应用名称
    debug=settings.DEBUG,  # 设置调试模式
)

# 配置CORS中间件
# 允许跨域资源共享，使前端应用能够安全地访问API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源访问
    allow_credentials=True,  # 允许携带认证信息
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)

# 注册路由
# 将视频处理任务相关的路由注册到应用
app.include_router(
    video_tasks.router,
    prefix=f"{settings.API_V1_STR}/video-tasks",  # 设置路由前缀
    tags=["视频处理任务"],  # 设置API文档标签
)


# 根路由
@app.get("/")
async def root():
    """根路由处理函数

    返回欢迎信息

    Returns:
        dict: 包含欢迎信息的字典
    """
    return {"message": f"Welcome to {settings.APP_NAME}!"}
