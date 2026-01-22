from typing import List, Any, Dict

from pydantic import BaseModel, Field

from src.schemas.enums import AnalysisMode

class AnalyzeRequest(BaseModel):
    project_id: str = Field(..., description="Unique identifier for the project context")
    analysis_mode: AnalysisMode = Field(
        default=AnalysisMode.SELLER_ASSISTANT,
        description="Type of persona to adopt for analysis"
    )
    contents: List[str] = Field(
        ..., 
        description="List of text content or GCS URIs to analyze"
    )

class AnalyzeResponse(BaseModel):
    project_id: str
    analysis_mode: AnalysisMode
    summary: str = Field(..., description="Natural language summary of the analysis")
    keywords: List[str] = Field(default_factory=list, description="Extracted key topics")
    insights: List[Dict[str, Any]] = Field(default_factory=list, description="Structured insights")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional processing metadata")

class FileValidationResult(BaseModel):
    source: str = Field(..., description="Source URI or path")
    is_valid: bool = Field(..., description="Whether the file passes validation")
    size_bytes: int = Field(..., description="File size in bytes")

class FileSizeValidationResponse(BaseModel):
    is_valid: bool = Field(..., description="Whether all files pass validation")
    max_size_bytes: int = Field(..., description="Maximum allowed file size in bytes")
    results: List[FileValidationResult] = Field(..., description="Validation results for each file")