from pydantic import BaseModel, Field

class ApiResponse(BaseModel):
    message: str = Field(..., description="Status message indicating the success of the operation.")
    results: str = Field(..., description="Remove label output")
    label_result: str = Field(..., description="Default output")