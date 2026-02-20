"""Viewer용 Pydantic 모델 정의 (ES 문서 조회용)"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SentimentType(str, Enum):
    """감정 유형"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ResultState(str, Enum):
    """분석 상태"""
    UNAVAILABLE = "UNAVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    FAIL = "FAIL"
    COMPLETED = "COMPLETED"


# === 분석 결과 모델 ===

class Highlight(BaseModel):
    """하이라이트 아이템"""
    id: int = Field(description="출처 콘텐츠 ID")
    keyword: str = Field(description="대표 키워드")
    highlight: str = Field(description="핵심 인사이트")
    content: str = Field(description="원본 콘텐츠")


class Category(BaseModel):
    """카테고리 분석 결과"""
    name: str = Field(description="카테고리 이름")
    key: str = Field(description="카테고리 키")
    summary: str = Field(description="카테고리 요약")
    keywords: List[str] = Field(default_factory=list, description="요약 키워드")
    display_highlight: str = Field(description="대표 하이라이트")
    sentiment_type: str = Field(description="감정 유형")  # 대소문자 호환을 위해 str로 변경
    positive_count: int = Field(default=0, description="긍정 하이라이트 수")
    negative_count: int = Field(default=0, description="부정 하이라이트 수")
    highlights: List[Highlight] = Field(default_factory=list, description="하이라이트 목록")

    @property
    def is_positive(self) -> bool:
        return self.sentiment_type.lower() == "positive"

    @property
    def is_negative(self) -> bool:
        return self.sentiment_type.lower() == "negative"


class AnalysisResult(BaseModel):
    """분석 결과 데이터"""
    summary: str = Field(description="전체 요약")
    keywords: List[str] = Field(default_factory=list, description="요약 키워드")
    good_points: List[str] = Field(default_factory=list, description="좋은 점")
    caution_points: List[str] = Field(default_factory=list, description="참고 사항")
    categories: List[Category] = Field(default_factory=list, description="카테고리 목록")


class ResultData(BaseModel):
    """ES 저장 분석 결과"""
    version: int = Field(default=1)
    meta_persona: Optional[str] = None
    meta_data: Optional[Any] = None
    persona: Optional[str] = None
    data: Optional[AnalysisResult] = None


class ResultDocument(BaseModel):
    """ES 분석 결과 문서"""
    project_id: str = Field(description="프로젝트 ID")
    project_type: Optional[str] = Field(default=None, description="프로젝트 타입")
    content_type: str = Field(description="콘텐츠 타입")
    version: int = Field(default=0, description="버전 번호")
    state: ResultState = Field(description="분석 상태")
    reason: Optional[str] = Field(default=None, description="사유")
    result: Optional[ResultData] = Field(default=None, description="분석 결과")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# === 프로젝트 정보 ===

@dataclass
class ProjectInfo:
    """프로젝트 기본 정보 (Wadiz API 조회 결과)"""
    project_id: int
    title: str
    thumbnail_url: str
    link: str
