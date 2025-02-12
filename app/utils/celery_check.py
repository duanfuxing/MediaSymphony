import redis
from celery.exceptions import OperationalError
from app.config import settings  # 直接使用 settings
from app.utils.logger import Logger

logger = Logger("video_tasks")


def check_celery_connection():
    """检查 Celery 和 Redis 连接"""
    try:
        # 直接使用配置中的值
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=0,  # broker 使用 db 0
            socket_timeout=5,
            socket_connect_timeout=5
        )
        
        # 测试 Redis 连接
        redis_client.ping()
        
        logger.info("Redis 连接成功")
        return True
        
    except redis.ConnectionError as e:
        logger.error("Redis 连接失败", {
            "error": str(e),
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT
        })
        return False
    except Exception as e:
        logger.error("Celery 检查出错", {"error": str(e)})
        return False