from pydantic import BaseModel, Field

class FileValidationResult(BaseModel):
    source: str = Field(..., description="Source URI or path")
    is_valid: bool = Field(..., description="Whether the file passes validation")
    size_bytes: int = Field(..., description="File size in bytes")