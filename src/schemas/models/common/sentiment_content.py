from pydantic import BaseModel, Field, field_validator
from typing import Union


class SentimentContent(BaseModel):
    """감정 분석이 포함된 콘텐츠 모델 - 평가 대상 기준"""
    
    id: int = Field(..., description="콘텐츠 고유 식별자")
    score: float = Field(..., description="평가 대상에 대한 감정 점수 (0.0~1.0 범위, 글이 평가하는 대상에 대한 감정)", ge=0.0, le=1.0)
    
    @field_validator('score')
    @classmethod
    def validate_sentiment_score(cls, v: Union[float, int]) -> float:
        """평가 대상에 대한 감정 점수 유효성 검증"""
        if not isinstance(v, (int, float)):
            raise ValueError("score는 숫자여야 합니다")
        
        score = float(v)
        if score < 0.0 or score > 1.0:
            raise ValueError("score는 0.0과 1.0 사이여야 합니다")
        
        return score