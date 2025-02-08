from celery import Celery
from app.config import settings

# 创建Celery实例
celery_app = Celery(
    "media_symphony",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",
)

# 配置Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_routes={"app.tasks.*": {"queue": "heavy_tasks"}},
    task_default_queue="heavy_tasks",
    # 任务结果过期时间
    result_expires=18000,
    # 工作进程预取任务数
    worker_prefetch_multiplier=1,
    # 限制任务执行时间
    task_time_limit=18000,
    # 软限制时间
    task_soft_time_limit=15000,
)
