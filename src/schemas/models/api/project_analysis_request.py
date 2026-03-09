from pydantic import BaseModel, Field

from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.content_type import ExternalContentType


class ProjectAnalysisRequest(BaseModel):
    """프로젝트 기반 콘텐츠 분석 요청"""
    project_id: int = Field(..., description="프로젝트 ID")
    content_type: ExternalContentType = Field(..., description="콘텐츠 타입 (REVIEW, SATISFACTION, SUPPORT, SUGGESTION)")
    analysis_mode: AnalysisMode = Field(
        default=AnalysisMode.REVIEW_BOT,
        description="분석 모드/페르소나"
    )
    refresh: bool = Field(
        default=False,
        description="True: 전체 콘텐츠 재분석, False: baseline 이후만 증분 분석"
    )