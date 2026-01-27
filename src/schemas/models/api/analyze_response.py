from typing import List, Any, Dict

from pydantic import BaseModel, Field

from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.project_type import ProjectType

class AnalyzeResponse(BaseModel):
    project_id: int
    project_type: ProjectType
    analysis_mode: AnalysisMode
    summary: str = Field(..., description="Natural language summary of the analysis")
    keywords: List[str] = Field(default_factory=list, description="Extracted key topics")
    insights: List[Dict[str, Any]] = Field(default_factory=list, description="Structured insights")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional processing metadata")