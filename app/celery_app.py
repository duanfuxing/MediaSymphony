from celery import Celery
from app.config import settings

# 创建Celery实例
celery_app = Celery(
    "media_symphony",
    broker=f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",
    broker_transport_options={
        'visibility_timeout': 3600,
        'socket_timeout': 30,
        'socket_connect_timeout': 30,
    }
)

# 配置Celery
celery_app.conf.update(
    # 基本配置
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    result_backend_transport_options={
        'retry_policy': {
            'timeout': 5.0
        }
    },
    
    task_default_queue="default",
    
    # 任务执行设置
    result_expires=18000,
    worker_prefetch_multiplier=1,
    task_time_limit=18000,
    task_soft_time_limit=15000,
    
    # Redis 配置
    broker_transport_options={
        'visibility_timeout': 3600,
        'socket_timeout': 30,
        'socket_connect_timeout': 30,
        'socket_keepalive': True,
        'retry_on_timeout': True
    },
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_connection_timeout=30,
    
    # 明确指定 broker 类型
    broker_transport='redis',
    result_backend_transport='redis',
)

# 自动发现任务
celery_app.autodiscover_tasks(['app'])
__all__ = ['celery_app', 'broker_url', 'result_backend']