from __future__ import annotations

from pydantic import BaseModel, Field


class CategorySummaryItem(BaseModel):
    """카테고리 요약 아이템 (정제 입력용)"""

    key: str = Field(..., description="카테고리 고유 키")
    summary: str = Field(..., description="카테고리 요약")
    keywords: list[str] = Field(
        default_factory=list,
        description="카테고리 요약의 핵심 키워드"
    )


class StructuredAnalysisSummary(BaseModel):
    """
    분석 요약 정제 입력 모델

    Note:
        get_content_analysis_summary_refine_prompt의 입력으로 사용됩니다.
        StructuredAnalysisRefinedSummary와 동일한 스키마를 가집니다.
    """

    summary: str = Field(..., description="전체 분석 요약")
    keywords: list[str] = Field(
        default_factory=list,
        description="전체 요약의 핵심 키워드"
    )
    good_points: list[str] = Field(
        default_factory=list,
        description="분석 결과에서 도출된 좋은 점 (최대 3개)"
    )
    caution_points: list[str] = Field(
        default_factory=list,
        description="참고할 만한 사항 (최대 2개)"
    )
    categories: list[CategorySummaryItem] = Field(..., description="카테고리별 요약 배열")
