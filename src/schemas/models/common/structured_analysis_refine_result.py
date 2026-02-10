from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.enums.sentiment_type import SentimentType


class RefineHighlightItem(BaseModel):
    """핵심 하이라이트 아이템 모델"""

    id: int = Field(..., description="이 하이라이트의 출처 콘텐츠 ID")
    keyword: str = Field(..., description="카테고리를 대표하는 원본 키워드")
    highlight: str = Field(..., description="카테고리의 본질을 포착하는 핵심 인사이트 또는 구절")
    content: str = Field(..., description="하이라이트의 출처가 되는 원본 콘텐츠 전체 텍스트")


class RefineCategoryItem(BaseModel):
    """카테고리 요약 아이템 (정제 입력용)"""

    name: str = Field(..., description="카테고리 이름")
    key: str = Field(..., description="카테고리 고유 키")
    summary: str = Field(..., description="카테고리 요약")
    display_highlight: str = Field(..., description="highlights 배열 중 카테고리를 가장 잘 대표하는 highlight")
    sentiment_type: SentimentType = Field(..., description="카테고리별 감정 유형")
    positive_count: int = Field(..., description="카테고리 내 positive highlights 개수")
    negative_count: int = Field(..., description="카테고리 내 negative highlights 개수")
    highlights: list[RefineHighlightItem] = Field(default_factory=list, description="핵심 하이라이트 배열")


class StructuredAnalysisRefineResult(BaseModel):
    """상세 분석 정제 결과 모델"""

    summary: str = Field(
        ..., description="발견된 모든 주요 주제와 인사이트를 다루는 포괄적인 분석 요약 (특수문자 Escape 필수)"
    )
    categories: list[RefineCategoryItem] = Field(..., description="카테고리별 상세 분석 결과 배열 (최대 20개)")
