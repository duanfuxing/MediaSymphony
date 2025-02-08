from fastapi import APIRouter, Form, UploadFile, HTTPException
from pydantic import HttpUrl, ValidationError
from typing import Optional
from models import ApiResponse
from audio_processor import AudioProcessor
from funasr.utils.postprocess_utils import rich_transcription_postprocess

router = APIRouter()
processor = AudioProcessor(model_dir="./iic/SenseVoiceSmall")

@router.post("/extract_text", response_model=ApiResponse)
async def upload_audio(
        url: Optional[HttpUrl] = Form(None),
        file: Optional[UploadFile] = Form(None),
        language: str = Form("zn")
):
    try:
        # 处理音频输入
        if file:
            audio_bytes = await file.read()
            audio_data = processor.process_audio_bytes(audio_bytes)
        elif url:
            audio_data = await processor.process_url(str(url))
        else:
            raise HTTPException(400, detail="No valid audio source provided.")

        # 生成转写结果
        res = processor.generate_text(
            audio_data=audio_data,
            language=language,
            use_itn=True
        )

        # 处理结果
        text = rich_transcription_postprocess(res[0]["text"])

        return {
            "message": "Audio processed successfully",
            "results": text,
            "label_result": res[0]["text"]
        }

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))