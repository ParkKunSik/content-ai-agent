from pydantic import BaseModel, Field


class EtcContent(BaseModel):
    """분석에서 제외된 기타 콘텐츠 모델"""
    
    content_id: int = Field(..., description="제외된 콘텐츠 ID")
    reason: str = Field(..., description="분석에서 제외된 이유 설명")