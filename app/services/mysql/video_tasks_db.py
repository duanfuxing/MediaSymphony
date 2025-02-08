from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.utils.logger import Logger

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
                    SELECT taskid, status, video_url, uid, 
                           scene_cut_output, audio_extract_output, text_convert_output,
                           error
                    FROM video_split_tasks
                    WHERE taskid = :taskid
                """
                )
                result = conn.execute(query, {"taskid": task_id}).fetchone()
                if result:
                    return {
                        "task_id": result.taskid,
                        "status": result.status,
                        "video_url": result.video_url,
                        "uid": result.uid,
                        "result": (
                            {
                                "scene_cut_output": result.scene_cut_output,
                                "audio_extract_output": result.audio_extract_output,
                                "text_convert_output": result.text_convert_output,
                            }
                            if result.scene_cut_output
                            or result.audio_extract_output
                            or result.text_convert_output
                            else None
                        ),
                        "error": result.error,
                    }
                return None
        except SQLAlchemyError as e:
            logger.error(f"获取任务失败: {str(e)}", {"task_id": task_id})
            return None

    def update_task_status(
        self, task_id: str, status: str, error: Optional[str] = None
    ) -> bool:
        """更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            error: 错误信息（可选）

        Returns:
            bool: 更新是否成功
        """
        try:
            with self.engine.connect() as conn:
                query = text(
                    """
                    UPDATE video_split_tasks
                    SET status = :status, error = :error
                    WHERE taskid = :taskid
                """
                )
                conn.execute(
                    query, {"taskid": task_id, "status": status, "error": error}
                )
                conn.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"更新任务状态失败: {str(e)}", {"task_id": task_id})
            return False

    def update_task_step_and_output(
        self, task_id: str, current_step: str, output_type: str, output_value: str
    ) -> bool:
        """更新任务执行步骤和对应的输出结果

        Args:
            task_id: 任务ID
            current_step: 当前执行步骤
            output_type: 输出类型（scene_cut_output/audio_extract_output/text_convert_output）
            output_value: 输出值

        Returns:
            bool: 更新是否成功
        """
        try:
            with self.engine.connect() as conn:
                query = text(
                    f"""
                    UPDATE video_split_tasks
                    SET current_step = :current_step,
                        {output_type} = :output_value
                    WHERE taskid = :taskid
                """
                )
                conn.execute(
                    query,
                    {
                        "taskid": task_id,
                        "current_step": current_step,
                        "output_value": output_value,
                    },
                )
                conn.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"更新任务步骤和输出失败: {str(e)}", {"task_id": task_id})
            return False
