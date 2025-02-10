import os
import logger
import uuid
import time
from fastapi import APIRouter
from models import SeparationResponse
from processor import AudioSeparatorProcessor
from config import settings

router = APIRouter()
processor = AudioSeparatorProcessor()

new_logger = logger.CustomLogger()


@router.post("/process/", response_model=SeparationResponse)
async def separate_audio(
        audio_path: str,
        model: str,
        task_id: str,
        output_path: str
):
    # 唯一请求ID
    request_id = uuid.uuid4().hex
    # 记录开始时间
    start_time = time.time()

    try:
        # 记录请求信息
        new_logger.info(f"Request received - task_id: {task_id}, model: {model}, audio_path: {audio_path}")

        # 处理音频文件
        output_files = processor.process_audio(audio_path, task_id, output_path)

        # 构建响应
        response = SeparationResponse(
            status="success",
            task_id=task_id,
            separated_audio={
                "vocals": os.path.basename(output_files[0]),
                "accompaniment": "accompaniment.wav"  # 需要processor支持accompaniment输出
            },
            file_paths={
                "vocals": output_files[0],
                "accompaniment": output_files[1] if len(output_files) > 1 else ""
            }
        )
        # 计算处理时间
        processing_time = time.time() - start_time


        new_logger.info(f"Request completed - task_id: {task_id}, response: {response}, processing_time: {processing_time}")
        return response
    # 捕获异常
    except Exception as e:
        new_logger.error(f"Request failed - task_id: {task_id}, error: {e}")

        # 返回失败响应
        return SeparationResponse(
            status="failed",
            task_id=task_id,
            message=str(e)
        )
