from typing import Optional
from pydantic import BaseModel, Field

class AnalysisContentItem(BaseModel):
    """상세 분석 프롬프트에 주입할 콘텐츠 아이템 모델"""
    
    id: int = Field(..., description="콘텐츠 고유 식별자 (프롬프트 최적화용)")
    content: str = Field(..., description="분석 대상 콘텐츠 텍스트")
    has_image: Optional[bool] = Field(default=None, description="이미지 포함 여부 (True인 경우에만 포함)")