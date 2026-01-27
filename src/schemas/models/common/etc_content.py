from pydantic import BaseModel, Field


class EtcContent(BaseModel):
    """분석에서 제외된 기타 콘텐츠 모델"""
    
    id: int = Field(..., description="콘텐츠 고유 식별자")
    reason: str = Field(..., description="분석에서 제외된 사유")