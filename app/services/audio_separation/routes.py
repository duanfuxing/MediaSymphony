import os
import logger
import uuid
import time
from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from models import ApiResponse
from processor import AudioSeparatorProcessor
from config import settings
from pydantic import ValidationError

# 配置日志

router = APIRouter()
processor = AudioSeparatorProcessor()

new_logger = logger.CustomLogger()


@router.post("/separate-audio/", response_model=ApiResponse)
async def separate_audio(
        model: str = Form(...),
        file: UploadFile = File(None),
        url: str = Form(None),
):
    # 唯一请求ID
    request_id = uuid.uuid4().hex
    # 记录开始时间
    start_time = time.time()

    try:
        # 记录请求信息
        new_logger.info(
            f"Request received - request_id: {request_id}, model: {model}, file: {file.filename if file else None}, url: {url}")

        if not file and not url:
            raise ValueError("Either file or url must be provided")
        if file and url:
            raise ValueError("Provide either file or url, not both")

        # 处理 url/file 保存到临时目录中
        temp_file_path = await processor.handle_input(file, url, request_id)
        # 处理音视频文件返回人声音频文件地址
        output_files = processor.process_audio(temp_file_path, model, request_id)
        new_logger.info(
            f"remove temp file: {temp_file_path}")
        # 删除临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        processing_time = time.time() - start_time

        response = ApiResponse(
            message="Audio separation completed successfully",
            output_files=[f"{settings.STATIC_SERVE_URL}/{settings.OUTPUT_DIR}/{file}" for file in output_files],
            request_id=request_id,
            processing_time=processing_time
        )
        new_logger.info(f"Request completed - request_id: {request_id}, response: {response}")
        return response

    except ValidationError as e:
        error_message = "Invalid input data"
        new_logger.error(f"Request failed - request_id: {request_id}, validation_error: {e}")
    except ValueError as e:
        error_message = str(e)
        new_logger.error(f"Request failed - request_id: {request_id}, error: {error_message}")
    except HTTPException as e:
        error_message = str(e)
        new_logger.error(f"Request failed - request_id: {request_id}, error: {error_message}")
    except Exception as e:
        error_message = str(e)
        new_logger.error(f"Unexpected error - request_id: {request_id}, error: {e}")

    processing_time = time.time() - start_time
    return ApiResponse(
        message=error_message,
        output_files=[],
        request_id=request_id,
        processing_time=processing_time
    )
