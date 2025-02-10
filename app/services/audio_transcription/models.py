from pydantic import BaseModel, Field
from typing import List

class Segment(BaseModel):
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")

class ApiResponse(BaseModel):
    status: str = Field(..., description="Response status, e.g., success or failure")
    task_id: str = Field(..., description="Unique task identifier")
    transcription: str = Field(..., description="Full transcribed text")
    transcription_path: str = Field(..., description="Path to the saved transcription file")
    segments: List[Segment] = Field(..., description="List of transcribed segments")
    message: str = Field(..., description="Additional message about the processing status")