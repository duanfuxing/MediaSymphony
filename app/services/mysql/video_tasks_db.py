from typing import Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy import create_engine, text, exc
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.utils.logger import Logger
import json
from functools import wraps
import time


logger = Logger("video_tasks_db")

def retry_on_connection_error(max_retries=3, initial_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exc.OperationalError as e:
                    if "Lost connection" in str(e) and attempt < max_retries - 1:
                        logger.warning(f"数据库连接丢失，正在重试 ({attempt + 1}/{max_retries})", {
                            "error": str(e),
                            "function": func.__name__
                        })
                        time.sleep(delay)
                        delay *= 2  # 指数退避
                        continue
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator


class VideoTasksDB:
    def __init__(self):
        db_url = f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=1800,  # 30分钟回收连接
            pool_size=10, # 5 * 2
            max_overflow=20 # 10 * 2
        )
    
    @retry_on_connection_error()
    def create_task(self, task_id: str, video_url: str, uid: str) -> bool:
        """创建新的视频处理任务

        Args:
            task_id: 任务ID
            video_url: 视频URL
            uid: 用户ID

        Returns:
            bool: 创建是否成功
        """
        try:
            with self.engine.connect() as conn:
                query = text(
                    """
                    INSERT INTO video_split_tasks (taskid, video_url, uid, status)
                    VALUES (:taskid, :video_url, :uid, 'pending')
                """
                )
                conn.execute(
                    query, {"taskid": task_id, "video_url": video_url, "uid": uid}
                )
                conn.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"创建任务失败: {str(e)}", {"task_id": task_id})
            return False

    @retry_on_connection_error()
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息

        Args:
            task_id: 任务ID

        Returns:
            Optional[Dict[str, Any]]: 任务信息，如果不存在则返回None
        """
        try:
            with self.engine.connect() as conn:
                query = text(
                    """
                    SELECT taskid, status, video_url, uid, task_progress, error
                    FROM video_split_tasks
                    WHERE taskid = :taskid
                """
                )
                result = conn.execute(query, {"taskid": task_id}).fetchone()
                if not result:
                    logger.info(f"任务不存在", {"task_id": task_id})
                    raise HTTPException(status_code=200, detail="任务不存在")
                try:
                    task_progress = json.loads(result.task_progress) if result.task_progress else {}
                except json.JSONDecodeError as e:
                    logger.error(f"task_progress JSON解析失败: {str(e)}", {
                        "task_id": task_id,
                        "task_progress": result.task_progress
                    })
                    raise HTTPException(status_code=200, detail="task_progress JSON解析失败")
                try:
                    error = json.loads(result.error) if result.error else None
                except json.JSONDecodeError as e:
                    logger.error(f"error字段 JSON解析失败: {str(e)}", {
                        "task_id": task_id,
                        "error": result.error
                    })
                    error = None
                    raise HTTPException(status_code=200, detail="error字段 JSON解析失败")
                
                return {
                    "task_id": result.taskid,
                    "status": result.status,
                    "video_url": result.video_url,
                    "uid": result.uid,
                    "result": task_progress,
                    "error": error,
                }
        except HTTPException as http_ex:
            raise http_ex
        except SQLAlchemyError as e:
            logger.error(f"获取任务失败: {str(e)}", {"task_id": task_id})
            raise HTTPException(status_code=500, detail="获取任务失败")
        except Exception as e:
            logger.error(f"获取任务时发生未预期的错误: {str(e)}", {
                "task_id": task_id,
                "error_type": type(e).__name__
            })
            raise HTTPException(status_code=500, detail="获取任务时发生未预期的错误")
        
    @retry_on_connection_error()
    def update_task_status(
        self, task_id: str, status: str, error: Optional[str] = None
    ) -> bool:
        """更新主任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            error: 错误信息（可选）

        Returns:
            bool: 更新是否成功
        """
        try:
            with self.engine.connect() as conn:
                error_json = json.dumps({"main": error}) if error else None
                query = text(
                    """
                    UPDATE video_split_tasks
                    SET status = :status, error = :error_json
                    WHERE taskid = :taskid
                """
                )
                conn.execute(
                    query,
                    {
                        "taskid": task_id,
                        "status": status,
                        "error_json": error_json,
                    },
                )
                conn.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"更新任务状态失败: {str(e)}", {"task_id": task_id})
            return False

    @retry_on_connection_error()
    def update_task_step_and_output(
        self,
        task_id: str,
        step: str,
        status: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """更新子任务状态和输出结果

        Args:
            task_id: 任务ID
            step: 子任务名称（scene_cut/audio_extract/text_convert）
            status: 子任务状态
            output: 输出结果（可选）
            error: 错误信息（可选）

        Returns:
            bool: 更新是否成功
        """
        try:
            with self.engine.connect() as conn:
                # 获取当前的task_progress和error
                query = text(
                    "SELECT task_progress, error FROM video_split_tasks WHERE taskid = :taskid"
                )
                result = conn.execute(query, {"taskid": task_id}).fetchone()
                if not result:
                    return False

                # 更新task_progress
                task_progress = json.loads(result.task_progress)
                task_progress[step] = {"status": status, "output": output}

                # 更新error（如果有）
                error_json = json.loads(result.error) if result.error else {}
                if error:
                    error_json[step] = error
                elif step in error_json:
                    del error_json[step]

                # 执行更新
                update_query = text(
                    """
                    UPDATE video_split_tasks
                    SET task_progress = :task_progress,
                        error = :error_json
                    WHERE taskid = :taskid
                """
                )
                conn.execute(
                    update_query,
                    {
                        "taskid": task_id,
                        "task_progress": json.dumps(task_progress),
                        "error_json": json.dumps(error_json) if error_json else None,
                    },
                )
                conn.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"更新任务步骤和输出失败: {str(e)}", {"task_id": task_id})
            return False
