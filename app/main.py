from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import video_tasks

# 创建FastAPI应用实例
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册路由
app.include_router(
    video_tasks.router,
    prefix=f"{settings.API_V1_STR}/video-tasks",
    tags=["视频处理任务"],
)


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}!"}
