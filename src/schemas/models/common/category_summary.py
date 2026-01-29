from __future__ import annotations
import logging
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from .sentiment_content import SentimentContent
from .highlight_item import HighlightItem
from ...enums.sentiment_type import SentimentType

logger = logging.getLogger(__name__)


class CategorySummary(BaseModel):
    """카테고리별 상세 분석 결과 모델"""
    
    category: str = Field(..., description="사용자가 이해할 수 있는 명확하고 설명적인 카테고리명")
    category_key: str = Field(..., description="카테고리를 snake_case 형태로 변환한 키값")
    sentiment_type: SentimentType = Field(..., description="카테고리별 감정 유형")
    summary: str = Field(..., description="상세한 카테고리 분석 및 인사이트")
    positive_contents: list[SentimentContent] = Field(default_factory=list, description="이 카테고리 내 긍정적 콘텐츠 배열 (평가 대상에 대한 감정 점수 0.5 이상)")
    negative_contents: list[SentimentContent] = Field(default_factory=list, description="이 카테고리 내 부정적 콘텐츠 배열 (평가 대상에 대한 감정 점수 0.5 미만)")
    highlights: list[HighlightItem] = Field(default_factory=list, description="핵심 하이라이트 배열")
    
    @field_validator('category_key')
    @classmethod
    def validate_category_key(cls, v: str, info: ValidationInfo) -> str:
        """카테고리명을 기반으로 snake_case 키 생성 및 검증"""
        data = info.data
        if 'category' in data:
            expected_key = data['category'].lower().replace(' ', '_').replace('-', '_')
            if v != expected_key:
                raise ValueError(f"category_key '{v}'이 category '{data['category']}'에서 생성된 예상 키 '{expected_key}'와 다릅니다")
        return v
    
    @field_validator('positive_contents')
    @classmethod
    def validate_positive_contents(cls, v: list[SentimentContent]) -> list[SentimentContent]:
        """긍정 콘텐츠의 평가 대상에 대한 감정 점수 검증 (0.5 이상 필수)"""
        invalid_contents = []
        for content in v:
            if content.score < 0.5:
                invalid_contents.append(f"id {content.id} (score: {content.score})")
        
        if invalid_contents:
            logger.warning(f"긍정 리스트에 0.5 미만 점수 포함: {', '.join(invalid_contents)}")
            # 프로덕션에서는 에러를 발생시키지 않지만 경고를 남김
        
        return v
    
    @field_validator('negative_contents')
    @classmethod
    def validate_negative_contents(cls, v: list[SentimentContent]) -> list[SentimentContent]:
        """부정 콘텐츠의 평가 대상에 대한 감정 점수 검증 (0.5 미만 필수)"""
        invalid_contents = []
        for content in v:
            if content.score >= 0.5:
                invalid_contents.append(f"id {content.id} (score: {content.score})")
        
        if invalid_contents:
            logger.warning(f"부정 리스트에 0.5 이상 점수 포함: {', '.join(invalid_contents)}")
            # 프로덕션에서는 에러를 발생시키지 않지만 경고를 남김
        
        return v
    
    @field_validator('sentiment_type')
    @classmethod
    def validate_sentiment_type(cls, v: SentimentType, info: ValidationInfo) -> SentimentType:
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
                    raise ValueError(f"sentiment_type '{v.value}'이 평균 점수 {avg_score:.2f}와 일치하지 않습니다. 예상: '{expected_type.value}'")
        
        return v