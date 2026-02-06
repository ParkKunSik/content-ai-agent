from __future__ import annotations

from pydantic import BaseModel, Field


class CategorySummaryItem(BaseModel):
    """카테고리 요약 아이템 (정제 입력용)"""

    key: str = Field(..., description="카테고리 고유 키")
    summary: str = Field(..., description="카테고리 요약")


class StructuredAnalysisSummary(BaseModel):
    """
    분석 요약 정제 입력 모델

    Note:
        get_content_analysis_summary_refine_prompt의 입력으로 사용됩니다.
        StructuredAnalysisRefinedSummary와 동일한 스키마를 가집니다.
    """

    summary: str = Field(..., description="전체 분석 요약")
    categories: list[CategorySummaryItem] = Field(..., description="카테고리별 요약 배열")
