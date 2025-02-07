from pydantic import BaseModel, Field
from typing import List

# 定义 api 返回体结构
class ApiResponse(BaseModel):
    message: str
    output_files: List[str]
    request_id: str = Field(..., description="Unique request ID")
    processing_time: float = Field(..., description="Processing time in seconds")
