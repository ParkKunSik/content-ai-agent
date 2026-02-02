from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """상세 분석을 위한 콘텐츠 아이템 모델"""
    
    content_id: int = Field(..., description="콘텐츠 고유 식별자")
    content: str = Field(..., description="분석 대상 콘텐츠 텍스트")
    has_image: bool = Field(default=False, description="이미지 포함 여부 (하이라이트 우선순위에 영향)")