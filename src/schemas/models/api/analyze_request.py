from __future__ import annotations

from typing import Union

from pydantic import BaseModel, Field

from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.project_type import ProjectType

from ..common.content_item import ContentItem


class AnalyzeRequest(BaseModel):
    project_id: int = Field(..., description="Unique identifier for the project context")
    project_type: ProjectType = Field(default=ProjectType.FUNDING_AND_PREORDER, description="Type of project (FUNDING, PREORDER, STORE)")
    analysis_mode: AnalysisMode = Field(
        default=AnalysisMode.REVIEW_BOT,
        description="Type of persona to adopt for analysis"
    )
    contents: list[Union[str, ContentItem]] = Field(
        ..., 
        description="List of text content, GCS URIs, or ContentItem objects to analyze"
    )