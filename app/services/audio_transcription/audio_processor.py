from io import BytesIO
import soundfile as sf
import librosa
from funasr import AutoModel
from config import settings
from io import BytesIO

class AudioProcessor:
    def __init__(self, model_dir: str, device: str = settings.CUDA_DEVICE):
        self.model = AutoModel(
            model=model_dir,
            trust_remote_code=True,
            remote_code="remote_code_model.py",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device=device,
        )

    def process_audio_bytes(self, audio_path: str) -> bytes:
        """处理音频文件并返回字节数据"""
        try:
            # 加载音频并重采样为 16kHz
            audio, _ = librosa.load(audio_path, sr=16000)
            
            # 创建内存缓冲区
            audio_buffer = BytesIO()
            
            # 将音频数据写入缓冲区
            sf.write(audio_buffer, audio, 16000, format='wav')
            
            # 获取字节数据
            audio_buffer.seek(0)
            return audio_buffer.read()
            
        except Exception as e:
            raise Exception(f"音频处理失败: {str(e)}")

    def generate_text(self, audio_data: str, language: str = "zn", use_itn: bool = True):
        """
        生成音频转写文本
        :param audio_data: 音频文件路径
        :param language: 语言代码
        :param use_itn: 是否使用 ITN
        :return: 转写结果
        """
        try:
            # 处理音频文件
            processed_audio = self.process_audio_bytes(audio_data)
            
            # 调用模型进行转写
            result = self.model.generate(
                input=processed_audio,
                language=language,
                use_itn=use_itn,
                batch_size_s=60,
                merge_vad=True,
                merge_length_s=15,
            )
            
            return result
            
        except Exception as e:
            raise Exception(f"转写失败: {str(e)}")
