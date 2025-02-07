from fastapi import HTTPException
import aiohttp
from io import BytesIO
import numpy as np
import librosa
from funasr import AutoModel

class AudioProcessor:
    def __init__(self, model_dir: str, device: str = "cuda:0"):
        self.model = AutoModel(
            model=model_dir,
            trust_remote_code=True,
            remote_code="./remote_code_model.py",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device=device,
        )

    async def process_url(self, url: str) -> np.ndarray:
        """从URL下载并处理音频"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
            ) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to download audio: {response.status}",
                    )
                audio_bytes = await response.read()
                return self.process_audio_bytes(audio_bytes)

    def process_audio_bytes(self, audio_bytes: bytes) -> np.ndarray:
        """处理音频字节数据"""
        audio_io = BytesIO(audio_bytes)
        waveform, sr = librosa.load(audio_io, sr=16000)  # 统一采样率为16kHz
        return waveform

    def generate_text(self,
                      audio_data: np.ndarray,
                      language: str = "zn",
                      use_itn: bool = True) -> dict:
        """生成文本转写结果"""
        return self.model.generate(
            input=audio_data,
            language=language,
            use_itn=use_itn,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
