from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.project_type import ProjectType

from ..common.content_item import ContentItem


class AnalyzeRequest(BaseModel):
    project_id: int = Field(..., description="Unique identifier for the project context")
    project_type: ProjectType = Field(default=ProjectType.FUNDING_AND_PREORDER, description="Type of project (FUNDING, PREORDER, STORE)")
    content_type: Optional[ExternalContentType] = Field(default=None, description="Type of content (REVIEW, SATISFACTION, etc.)")
    analysis_mode: AnalysisMode = Field(
        default=AnalysisMode.REVIEW_BOT,
        description="Type of persona to adopt for analysis"
    )
    contents: List[ContentItem] = Field(
        ...,
        description="List of ContentItem objects to analyze (content_id required for traceability)"
    )