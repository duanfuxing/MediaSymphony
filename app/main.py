from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.config import settings
from app.routers import video_tasks
from app.utils.logger import Logger
import logging
from typing import Any
from typing import List

logger = Logger("video_tasks")

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,  # 设置应用名称
    debug=settings.DEBUG,  # 设置调试模式
)

# 配置 uvicorn 访问日志级别
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# 配置CORS中间件
# 允许跨域资源共享，使前端应用能够安全地访问API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源访问
    allow_credentials=True,  # 允许携带认证信息
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_paths=None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or []
        self.valid_tokens = settings.X_TOKEN if isinstance(settings.X_TOKEN, list) else [settings.X_TOKEN]

    async def dispatch(self, request: Request, call_next):
        try:
            if any(request.url.path.startswith(path) for path in self.exclude_paths):
                return await call_next(request)

            token = request.headers.get("x-token")
            if not token:
                return JSONResponse(
                    status_code=401,
                )
            
            if token not in self.valid_tokens:
                return JSONResponse(
                    status_code=403,
                )

            return await call_next(request)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"detail": "服务器内部错误"}
            )

# 注册路由
# 将视频处理任务相关的路由注册到应用
app.include_router(
    video_tasks.router, 
    prefix=f"{settings.API_V1_STR}/video-tasks",  # 设置路由前缀
    tags=["视频处理任务"],  # 设置API文档标签
)

app.add_middleware(
    AuthMiddleware,
    exclude_paths=[]  # 排除 Swagger 文档路径
)

# 参数验证异常处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        error_fields = []
        for error in exc.errors():
            if error["type"] == "missing":
                field = error["loc"][-1]
                error_fields.append(field)
        
        error_message = f"缺少必填参数: {', '.join(error_fields)}" if error_fields else "参数验证错误"
        
        # 记录请求信息和错误
        logger.error(
            f"参数验证错误 - 路径: {request.url.path} - 错误: {error_message}"
        )
        
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": error_message
            }
        )
    except Exception as e:
        logger.error(f"处理参数验证异常时出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": "服务错误"
            }
        )
    
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    try:
        logger.warning(
            f"HTTP异常 - 路径: {request.url.path}\n"
            f"状态码: {exc.status_code}\n"
            f"详情: {exc.detail}"
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "error": exc.detail
            }   
        )
    except Exception as e:
        logger.error(f"处理HTTP异常时出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": "服务错误"
            }
        )

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    try:
        error_msg = "服务错误"
        status_code = 500
        
        # 处理 HTTPException
        if isinstance(exc, HTTPException):
            error_msg = exc.detail
            status_code = exc.status_code
        # 处理其他异常类型
        elif isinstance(exc, ValueError):
            error_msg = "参数值错误"
            status_code = 400
        elif isinstance(exc, FileNotFoundError):
            error_msg = "文件未找到"
            status_code = 404
        
        # 记录日志
        logger.error(
            f"请求异常 - 路径: {request.url.path}\n"
            f"异常类型: {type(exc).__name__}\n"
            f"异常信息: {str(exc)}\n"
        )
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "error",
                "error": error_msg
            }
        )
    except Exception as e:
        logger.critical(
            f"全局异常处理器发生错误: {str(e)}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": "服务错误"
            }
        )

# 包装路由处理函数，添加异常保护
def safe_endpoint(func: Any):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"路由处理发生异常: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": "服务错误"
                }
            )
    return wrapper

# 对于所有的路由处理函数，建议都添加 @safe_endpoint 装饰器：
# @app.post("/some-endpoint")
# @safe_endpoint
# async def some_endpoint():
#     # 你的代码
#     pass

# 根路由
@app.get("/")
async def root():
    """根路由处理函数

    返回欢迎信息

    Returns:
        dict: 包含欢迎信息的字典
    """
    return {"message": f"Welcome to {settings.APP_NAME}!"}
