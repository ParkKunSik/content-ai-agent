from pydantic import BaseModel, Field, field_validator
from typing import Union


class SentimentContent(BaseModel):
    """감정 분석이 포함된 콘텐츠 모델"""
    
    content_id: int = Field(..., description="콘텐츠 고유 식별자")
    sentiment_score: float = Field(..., description="감정 점수 (0.0~1.0 범위)", ge=0.0, le=1.0)
    
    @field_validator('sentiment_score')
    @classmethod
    def validate_sentiment_score(cls, v: Union[float, int]) -> float:
        """감정 점수 유효성 검증"""
        if not isinstance(v, (int, float)):
            raise ValueError("sentiment_score는 숫자여야 합니다")
        
        score = float(v)
        if score < 0.0 or score > 1.0:
            raise ValueError("sentiment_score는 0.0과 1.0 사이여야 합니다")
        
        return score