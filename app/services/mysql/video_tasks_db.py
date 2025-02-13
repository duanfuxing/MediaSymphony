from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.utils.logger import Logger
import json

logger = Logger("video_tasks_db")


class VideoTasksDB:
    def __init__(self):
        # 构建数据库连接URL
        db_url = f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        self.engine = create_engine(db_url)

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
                    raise Exception(status_code=404, detail="任务不存在")
                try:
                    task_progress = json.loads(result.task_progress) if result.task_progress else {}
                except json.JSONDecodeError as e:
                    logger.error(f"task_progress JSON解析失败: {str(e)}", {
                        "task_id": task_id,
                        "task_progress": result.task_progress
                    })
                    raise Exception(status_code=404, detail="task_progress JSON解析失败")
                try:
                    error = json.loads(result.error) if result.error else None
                except json.JSONDecodeError as e:
                    logger.error(f"error字段 JSON解析失败: {str(e)}", {
                        "task_id": task_id,
                        "error": result.error
                    })
                    error = None
                    raise Exception(status_code=404, detail="error字段 JSON解析失败")
                
                return {
                    "task_id": result.taskid,
                    "status": result.status,
                    "video_url": result.video_url,
                    "uid": result.uid,
                    "result": task_progress,
                    "error": error,
                }
        except SQLAlchemyError as e:
            logger.error(f"获取任务失败: {str(e)}", {"task_id": task_id})
            raise Exception(status_code=500, detail="获取任务失败")
        except Exception as e:
            logger.error(f"获取任务时发生未预期的错误: {str(e)}", {
                "task_id": task_id,
                "error_type": type(e).__name__
            })
            raise Exception(status_code=500, detail="获取任务时发生未预期的错误")

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
