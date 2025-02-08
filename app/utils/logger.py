import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any


class Logger:
    def __init__(self, app_name: str = "app"):
        self.logger = None
        self.app_name = app_name
        self.setup_logger()

    def setup_logger(self):
        # 获取当前日期
        now = datetime.now()
        year_month = now.strftime("%Y/%m")
        day = now.strftime("%d")

        # 创建日志目录
        log_dir = os.path.join("log", year_month)
        os.makedirs(log_dir, exist_ok=True)

        # 设置日志文件路径
        log_file = os.path.join(log_dir, f"{day}.log")

        # 创建logger
        self.logger = logging.getLogger(self.app_name)
        self.logger.setLevel(logging.DEBUG)

        # 清除现有的处理器
        if self.logger.handlers:
            self.logger.handlers.clear()

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 设置日志格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(extra_data)s"
        )

        # 添加自定义过滤器来处理extra_data
        class ExtraDataFilter(logging.Filter):
            def filter(self, record):
                if not hasattr(record, "extra_data"):
                    record.extra_data = ""
                return True

        self.logger.addFilter(ExtraDataFilter())

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _log(self, level: int, message: str, extra: Optional[Dict[str, Any]] = None):
        if extra is None:
            extra = {}
        extra_str = str(extra) if extra else ""
        self.logger.log(level, message, extra={"extra_data": extra_str})

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.DEBUG, message, extra)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.INFO, message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.WARNING, message, extra)

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.ERROR, message, extra)

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.CRITICAL, message, extra)

    # 通用的日志方法
    def log_request(
        self, method: str, url: str, extra: Optional[Dict[str, Any]] = None
    ):
        info = {"method": method, "url": url}
        if extra:
            info.update(extra)
        self.info("API请求", info)

    def log_response(
        self, status_code: int, url: str, extra: Optional[Dict[str, Any]] = None
    ):
        info = {"status_code": status_code, "url": url}
        if extra:
            info.update(extra)
        self.info("API响应", info)

    def log_task_status(
        self, task_id: str, status: str, extra: Optional[Dict[str, Any]] = None
    ):
        info = {"task_id": task_id, "status": status}
        if extra:
            info.update(extra)
        self.info("任务状态更新", info)
