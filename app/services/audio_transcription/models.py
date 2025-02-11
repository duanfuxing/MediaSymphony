from pydantic import BaseModel, Field
from typing import List, Optional

class Segment(BaseModel):
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")

class ApiResponse(BaseModel):
    status: str = Field(..., description="Response status, e.g., success or failure")
    task_id: str = Field(..., description="Unique task identifier")
    message: Optional[str] = Field(None, description="Additional message about the processing status")
    transcription: Optional[str] = Field(None, description="Full transcribed text")
    transcription_path: Optional[str] = Field(None, description="Path to the saved transcription file")
    segments: Optional[List[Segment]] = Field(None, description="List of transcribed segments")