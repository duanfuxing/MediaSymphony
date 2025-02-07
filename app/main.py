from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

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

# 导入路由模块
from app.routers import audio_separation, audio_transcription, video_scene_split

# 注册路由
app.include_router(
    audio_separation.router,
    prefix=f"{settings.API_V1_STR}/audio-separation",
    tags=["音频分离"],
)

app.include_router(
    audio_transcription.router,
    prefix=f"{settings.API_V1_STR}/audio-transcription",
    tags=["音频转文字"],
)

app.include_router(
    video_scene_split.router,
    prefix=f"{settings.API_V1_STR}/video-scene-split",
    tags=["视频场景分割"],
)


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}!"}
