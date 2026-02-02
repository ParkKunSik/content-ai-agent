from pydantic import BaseModel, Field


class EtcContent(BaseModel):
    """분석에서 제외된 기타 콘텐츠 모델"""
    
    id: int = Field(..., description="분석에서 제외된 콘텐츠의 고유 ID")
    reason: str = Field(..., description="분석에 포함하지 않은 구체적인 사유 (예: 단순 인사말, 의미 없는 반복 등)")