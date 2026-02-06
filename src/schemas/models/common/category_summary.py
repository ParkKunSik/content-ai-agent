from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from src.core.config import settings

from ...enums.sentiment_type import SentimentType
from .highlight_item import HighlightItem
from .sentiment_content import SentimentContent

logger = logging.getLogger(__name__)


class CategorySummary(BaseModel):
    """
    카테고리별 상세 분석 결과 모델
    
    Note:
        이 모델은 'DetailedAnalysisResponse'의 하위 모델로서,
        API의 'response_schema'를 통해 LLM에게 카테고리 분석 지침을 전달합니다.
        필드 설명(description)은 LLM이 데이터를 추출하고 분류하는 기준이 됩니다.
    """
    
    category: str = Field(..., description="사용자가 이해할 수 있는 명확하고 설명적인 카테고리명 (콘텐츠와 동일한 언어 사용)")
    category_key: str = Field(..., description="category의 공백을 '_'로 대체한 키값 (기타 변형 없이 대소문자 유지, 예: 'Product Quality' -> 'Product_Quality')")
    display_highlight: str = Field(..., description="highlights 배열 중 카테고리를 가장 잘 대표하는 highlight의 keyword 값 (highlights[].keyword에서 선택, 그대로 복사)")
    sentiment_type: SentimentType = Field(..., description="카테고리별 감정 유형 (평균 점수 기준: negative < 0.45, positive >= 0.55, neutral 0.45 ~ 0.55)")
    summary: str = Field(..., description="상세한 카테고리 분석 및 인사이트")
    positive_contents: list[SentimentContent] = Field(default_factory=list, description="평가 대상에 대한 감정 점수가 0.5 이상인 긍정적 콘텐츠 리스트")
    negative_contents: list[SentimentContent] = Field(default_factory=list, description="평가 대상에 대한 감정 점수가 0.5 미만인 부정적 콘텐츠 리스트")
    highlights: list[HighlightItem] = Field(default_factory=list, description="핵심 하이라이트 배열 (원문 언어 유지, 번역 금지)")
    
    @field_validator('category_key')
    @classmethod
    def validate_category_key(cls, v: str, info: ValidationInfo) -> str:
        if not settings.STRICT_VALIDATION:
            return v

        """카테고리명을 기반으로 공백만 '_'로 대체한 키 생성 및 검증"""
        data = info.data
        if 'category' in data:
            expected_key = data['category'].replace(' ', '_')
            if v != expected_key:
                error_msg = f"category_key '{v}'이 category '{data['category']}'에서 생성된 예상 키 '{expected_key}'와 다릅니다"
                raise ValueError(error_msg)
        return v
    
    @field_validator('positive_contents')
    @classmethod
    def validate_positive_contents(cls, v: list[SentimentContent]) -> list[SentimentContent]:
        if not settings.STRICT_VALIDATION:
            return v

        """긍정 콘텐츠의 평가 대상에 대한 감정 점수 검증 (0.5 이상 필수)"""
        invalid_contents = []
        for content in v:
            if content.score < 0.5:
                invalid_contents.append(f"id {content.id} (score: {content.score})")
        
        if invalid_contents:
            error_msg = f"긍정 리스트에 0.5 미만 점수 포함: {', '.join(invalid_contents)}"
            raise ValueError(error_msg)
        
        return v
    
    @field_validator('negative_contents')
    @classmethod
    def validate_negative_contents(cls, v: list[SentimentContent]) -> list[SentimentContent]:
        if not settings.STRICT_VALIDATION:
            return v

        """부정 콘텐츠의 평가 대상에 대한 감정 점수 검증 (0.5 미만 필수)"""
        invalid_contents = []
        for content in v:
            if content.score >= 0.5:
                invalid_contents.append(f"id {content.id} (score: {content.score})")
        
        if invalid_contents:
            error_msg = f"부정 리스트에 0.5 이상 점수 포함: {', '.join(invalid_contents)}"
            raise ValueError(error_msg)
        
        return v
    
    @field_validator('sentiment_type')
    @classmethod
    def validate_sentiment_type(cls, v: SentimentType, info: ValidationInfo) -> SentimentType:
        if not settings.STRICT_VALIDATION:
            return v

        """감정 타입과 평가 대상에 대한 콘텐츠 감정 점수 일관성 검증"""
        data = info.data
        if 'positive_contents' in data and 'negative_contents' in data:
            pos_contents = data['positive_contents']
            neg_contents = data['negative_contents']
            pos_count = len(pos_contents)
            neg_count = len(neg_contents)
            total_count = pos_count + neg_count
            
            if total_count > 0:
                avg_score = 0.0
                for content in pos_contents:
                    avg_score += content.score
                for content in neg_contents:
                    avg_score += content.score
                avg_score = avg_score / total_count
                
                expected_type = SentimentType.from_average_score(avg_score)
                if v != expected_type:
                    error_msg = f"sentiment_type '{v.value}'이 평균 점수 {avg_score:.2f}와 일치하지 않습니다. 예상: '{expected_type.value}'"
                    raise ValueError(error_msg)
        
        return v