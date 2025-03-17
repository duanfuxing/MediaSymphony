from config import settings
from audio_separator.separator import Separator
import os
import subprocess
import shutil
import logger

new_logger = logger.CustomLogger()

class AudioSeparatorProcessor:
    def __init__(self):
        self.separator = Separator(
            output_single_stem="Vocals",
            model_file_dir=settings.MODEL_DIR
        )
        # 检查ffmpeg是否可用
        self.ffmpeg_available = self._check_ffmpeg_available()
        if not self.ffmpeg_available:
            new_logger.warning("ffmpeg不可用，备选方案将无法使用")

    def _check_audio_stream(self, file_path):
        """
        检查文件是否包含音频流
        
        Args:
            file_path: 输入文件路径
            
        Returns:
            bool: 是否包含音频流
        """
        try:
            cmd = [
                "/usr/bin/ffmpeg",
                "-i", file_path,
                "-af", "volumedetect",
                "-f", "null",
                "-"
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            # 检查ffmpeg输出中是否包含音频流信息
            return "Stream #0:0: Audio" in result.stderr or "Stream #0:1: Audio" in result.stderr
        except Exception as e:
            new_logger.warning(f"检查音频流时出错: {str(e)}")
            return False

    def process_audio(self, aduio_path: str, task_id: str, output_path):
        # 判断 output_path 目录是否存在，不存在创建
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        new_logger.info(f"开始处理音频文件: {aduio_path}, 任务ID: {task_id}")
        
        # 检查是否包含音频流
        has_audio = self._check_audio_stream(aduio_path)
        if not has_audio:
            new_logger.warning(f"文件不包含音频流: {aduio_path}")
            return {
                "has_audio_stream": False,
                "vocals": "",
                "accompaniment": ""
            }
        
        try:
            # 实例化 separator 类
            self.separator = Separator(
                output_single_stem="Vocals",
                model_file_dir=settings.MODEL_DIR,
                output_dir=output_path
            )

            new_logger.info(f"加载模型: {settings.MODEL_FILENAME}")
            self.separator.load_model(model_filename=settings.MODEL_FILENAME)
            
            # 修改输出文件的命名
            output_names = {
                "Vocals": f"vocals_{task_id}",
                "Instrumental": f"accompaniment_{task_id}"
            }
            
            # 尝试进行音频分离
            result_paths = self.separator.separate(aduio_path, output_names)
            return {
                "has_audio_stream": True,
                "vocals": result_paths[0],
                "accompaniment": result_paths[1]
            }
            
        except Exception as e:
            # 音频分离失败，使用ffmpeg提取原始音频作为备选方案
            new_logger.error(f"音频分离失败: {str(e)}，使用ffmpeg提取原始音频作为备选方案")
            
            # 检查ffmpeg是否可用
            if not self.ffmpeg_available:
                new_logger.error("ffmpeg不可用，无法使用备选方案")
                raise Exception(f"音频处理失败，且ffmpeg不可用: {str(e)}")
            
            # 定义输出文件路径
            vocals_output_path = os.path.join(output_path, f"vocals_{task_id}.mp3")
            
            try:
                # 使用ffmpeg提取音频
                self._extract_audio_with_ffmpeg(aduio_path, vocals_output_path)
                
                if os.path.exists(vocals_output_path):
                    new_logger.info(f"使用ffmpeg提取音频成功: {vocals_output_path}")
                    return {
                        "has_audio_stream": True,
                        "vocals": vocals_output_path,
                        "accompaniment": vocals_output_path
                    }
                else:
                    raise Exception("使用ffmpeg提取音频失败")
            except Exception as ffmpeg_error:
                new_logger.error(f"使用ffmpeg提取音频失败: {str(ffmpeg_error)}")
                raise Exception(f"音频处理失败，备选方案也失败: {str(e)}. ffmpeg错误: {str(ffmpeg_error)}")
    
    def _check_ffmpeg_available(self):
        """
        检查ffmpeg是否可用
        
        Returns:
            bool: ffmpeg是否可用
        """
        # 方法1：使用shutil.which检查ffmpeg是否在PATH中
        if shutil.which("/usr/bin/ffmpeg"):
            new_logger.info("ffmpeg在PATH中可用")
            return True
        
        # 方法2：尝试运行ffmpeg命令
        try:
            result = subprocess.run(
                ["/usr/bin/ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if result.returncode == 0:
                new_logger.info(f"ffmpeg可用，版本信息: {result.stdout.splitlines()[0]}")
                return True
            else:
                new_logger.warning(f"ffmpeg命令返回非零状态码: {result.returncode}")
                return False
        except Exception as e:
            new_logger.warning(f"检查ffmpeg可用性时出错: {str(e)}")
            return False
    
    def _extract_audio_with_ffmpeg(self, input_path, output_path):
        """
        使用ffmpeg从视频或音频文件中提取音频
        
        Args:
            input_path: 输入文件路径
            output_path: 输出音频文件路径
        """
        new_logger.info(f"使用ffmpeg从 {input_path} 提取音频到 {output_path}")
        
        # 构建ffmpeg命令
        cmd = [
            "/usr/bin/ffmpeg",
            "-i", input_path,
            "-vn",  # 不处理视频
            "-acodec", "libmp3lame",
            "-ar", "44100",  # 采样率44.1kHz
            "-y",  # 覆盖已存在的文件
            output_path
        ]
        
        # 执行命令
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            new_logger.info(f"ffmpeg命令执行成功: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            new_logger.error(f"ffmpeg命令执行失败: {e.stderr}")
            raise Exception(f"ffmpeg命令执行失败: {e.stderr}")