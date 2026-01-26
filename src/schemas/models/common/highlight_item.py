from pydantic import BaseModel, Field


class HighlightItem(BaseModel):
    """핵심 하이라이트 아이템 모델"""
    
    content_id: int = Field(..., description="하이라이트의 출처가 되는 콘텐츠 ID")
    org_keyword: str = Field(..., description="하이라이트의 근거가 되는 원본 키워드/구문 (번역하지 않은 원문)")
    highlight: str = Field(..., description="카테고리의 본질을 포착하는 핵심 인사이트 또는 대표적 진술 (번역하지 않은 원문)")