"""Viewer용 Pydantic 모델 정의 (ES 문서 조회용)"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, computed_field


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


# === LLM 사용 정보 ===

class LLMUsageInfo(BaseModel):
    """LLM 호출별 사용 정보"""
    step: int = Field(description="분석 단계 번호")
    model: str = Field(description="모델명")
    input_tokens: int = Field(default=0, description="입력 토큰 수")
    output_tokens: int = Field(default=0, description="출력 토큰 수")
    duration_ms: int = Field(default=0, description="소요 시간 (밀리초)")
    input_cost: Optional[float] = Field(default=None, description="입력 토큰 비용 (USD)")
    output_cost: Optional[float] = Field(default=None, description="출력 토큰 비용 (USD)")
    total_cost: Optional[float] = Field(default=None, description="총 비용 (USD)")

    @computed_field
    @property
    def total_tokens(self) -> int:
        """총 토큰 수"""
        return self.input_tokens + self.output_tokens


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
    llm_usages: List[LLMUsageInfo] = Field(default_factory=list, description="LLM 사용 정보")
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


# === 비교 뷰어용 모델 ===

@dataclass
class CompareResultItem:
    """비교 뷰어용 결과 아이템"""
    project_id: str
    content_type: str
    project_info: Optional[ProjectInfo] = None
    vertex_ai: Optional["ResultDocument"] = None
    openai: Optional["ResultDocument"] = None

    @property
    def has_both(self) -> bool:
        """양쪽 모두 데이터가 있는지"""
        return self.vertex_ai is not None and self.openai is not None

    @property
    def has_any(self) -> bool:
        """한쪽이라도 데이터가 있는지"""
        return self.vertex_ai is not None or self.openai is not None


@dataclass
class CompareProjectItem:
    """비교 목록용 프로젝트 아이템"""
    project_id: str
    project_info: Optional[ProjectInfo] = None
    content_types: List[str] = field(default_factory=list)
    has_vertex_ai: bool = False
    has_openai: bool = False

    @property
    def has_both(self) -> bool:
        """양쪽 모두 데이터가 있는지"""
        return self.has_vertex_ai and self.has_openai
