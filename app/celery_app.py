from celery import Celery
from app.config import settings

class TaskRouter:
    def route_for_task(self, task_name, args=None, kwargs=None):
        if task_name == 'app.tasks.process_video':
            # 尝试从 kwargs 中获取 uid
            if kwargs and 'uid' in kwargs:
                uid = kwargs['uid']
            # 如果在 kwargs 中找不到，尝试从 args 中获取
            elif args and len(args) > 2:
                uid = args[2]
            else:
                # 如果都找不到，使用默认队列
                return {'queue': 'person'}
            
            # 根据 uid 决定队列
            return {
                'queue': 'batch' if uid == '0' else 'person'
            }
        return None

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
    redis_backend_health_check_interval = 5,
    
    # 队列配置
    task_default_queue="person",  # 默认队列改为 person
    task_queues={
        'batch': {
            'exchange': 'batch',
            'routing_key': 'batch'
        },
        'person': {
            'exchange': 'person',
            'routing_key': 'person'
        }
    },
    task_routes=(TaskRouter(),),  # 使用自定义路由类
    
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
