from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """상세 분석을 위한 콘텐츠 아이템 모델"""

    content_id: int = Field(..., description="콘텐츠 고유 식별자")
    content: str = Field(..., description="분석 대상 콘텐츠 텍스트")
    has_image: bool = Field(default=False, description="이미지 포함 여부 (하이라이트 우선순위에 영향)")
    created_at: Optional[datetime] = Field(
        default=None,
        description="콘텐츠 생성 시간 (ES 데이터에서 전달)"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="콘텐츠 수정 시간 (ES 데이터에서 전달)"
    )