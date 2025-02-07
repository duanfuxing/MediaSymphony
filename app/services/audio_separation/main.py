from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from routes import router
from config import settings

# 初始化 fastapi
app = FastAPI(title="Audio Separator API", version="1.0.0")

# cors 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 引用路由
app.include_router(router)

# 确保目录存在
dirs_to_check = [
    settings.MODEL_DIR,
    settings.OUTPUT_DIR,
    settings.TEMP_DIR
]

for directory in dirs_to_check:
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"目录 {directory} 已创建")
    else:
        print(f"目录 {directory} 已存在")

# 启动服务
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
