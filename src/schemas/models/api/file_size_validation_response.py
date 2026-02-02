from typing import List

from pydantic import BaseModel, Field

from .file_validation_result import FileValidationResult

class FileSizeValidationResponse(BaseModel):
    is_valid: bool = Field(..., description="Whether all files pass validation")
    max_size_bytes: int = Field(..., description="Maximum allowed file size in bytes")
    results: List[FileValidationResult] = Field(..., description="Validation results for each file")