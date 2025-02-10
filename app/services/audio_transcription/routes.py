from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from models import ApiResponse
from audio_processor import AudioProcessor
from funasr.utils.postprocess_utils import rich_transcription_postprocess
import os
import traceback
import logger

router = APIRouter()
processor = AudioProcessor(model_dir="./iic/SenseVoiceSmall")
new_logger = logger.CustomLogger()

class AudioRequest(BaseModel):
    audio_path: str
    output_path: str
    task_id: str
    language: str = "zn"  # 可选，默认 "zn"
    model: str = "medium"  # 可选，默认 "medium"

@router.post("/api/v1/audio-transcription/process", response_model=ApiResponse)
async def upload_audio(request: AudioRequest):
    try:
        # 验证输入路径
        if not os.path.exists(request.audio_path):
            return ApiResponse(
                status="error",
                task_id=request.task_id,
                message=f"输入文件不存在: {request.audio_path}",
                transcription=None,
                transcription_path=None,
                segments=None
            )
        
        # 验证输出路径
        try:
            os.makedirs(request.output_path, exist_ok=True)
        except Exception as e:
            return ApiResponse(
                status="error",
                task_id=request.task_id,
                message=f"无法创建输出目录 {request.output_path}: {str(e)}",
                transcription=None,
                transcription_path=None,
                segments=None
            )

        # 验证输出路径的写入权限
        if not os.access(request.output_path, os.W_OK):
            return ApiResponse(
                status="error",
                message=f"输出目录无写入权限: {request.output_path}",
                task_id=request.task_id
            )
        
         # 验证输入文件格式
        file_ext = os.path.splitext(request.audio_path)[1].lower()
        if file_ext not in ['.mp3', '.wav', '.m4a', '.flac', '.ogg']:
            return ApiResponse(
                status="error",
                message=f"不支持的文件格式: {file_ext}",
                task_id=request.task_id
            )
        
        # 验证文件大小
        try:
            file_size = os.path.getsize(request.audio_path)

            max_size = 100 * 1024 * 1024  # 100MB
            if file_size > max_size:
                return ApiResponse(
                    status="error",
                    message=f"文件大小超过限制(100MB): {file_size/1024/1024:.2f}MB",
                    task_id=request.task_id
                )
        except Exception as e:
            return ApiResponse(
                status="error",
                message=f"无法获取文件大小: {str(e)}",
                task_id=request.task_id
            )


        # 生成转写结果
        try:
            res = processor.generate_text(
                audio_data=request.audio_path,
                language=request.language,
                use_itn=True
            )

             # 处理结果
            text = rich_transcription_postprocess(res[0]["text"])
            # 将text结果写入到output_path中, 文件格式为 task_id.txt 
            output_file = os.path.join(request.output_path, f"{request.task_id}.txt")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text)

            # 成功情况下的返回
            return ApiResponse(
                status="success",
                task_id=request.task_id,
                message="转写成功",
                transcription=text,  # 实际的转写文本
                transcription_path=output_file,  # 保存的文件路径
                segments=res[0].get("segments", None)  # 如果有分段信息的话
            )
        except Exception as e:
            error_detail = traceback.format_exc()
            new_logger.error(f"未预期的错误 - task_id: {request.task_id}\n{error_detail}")
            
            return ApiResponse(
                status="error",
                task_id=request.task_id,
                message=f"服务器内部错误: {str(e)}",
                transcription=None,
                transcription_path=None,
                segments=None
            )

    except Exception as e:
        # 捕获所有未预期的异常
        error_detail = traceback.format_exc()
        new_logger.error(f"未预期的错误 - task_id: {request.task_id}\n{error_detail}")
        
        return ApiResponse(
            status="error",
            task_id=request.task_id,
            message=f"服务器内部错误: {str(e)}",
            transcription=None,
            transcription_path=None,
            segments=None
        )