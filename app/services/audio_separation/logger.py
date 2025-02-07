import os
import logging
from datetime import datetime


class CustomLogger:
    def __init__(self):
        self.logger = None
        self.setup_logger()

    def setup_logger(self):
        # 获取当前日期
        now = datetime.now()
        year_month = now.strftime('%Y/%m')
        day = now.strftime('%d')

        # 创建日志目录
        log_dir = os.path.join('log', year_month)
        os.makedirs(log_dir, exist_ok=True)

        # 设置日志文件路径
        log_file = os.path.join(log_dir, f'audio_separator{day}.log')

        # 创建logger
        self.logger = logging.getLogger('audio-separator')
        self.logger.setLevel(logging.DEBUG)

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 添加处理器
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)