from pydantic import BaseModel, Field


class HighlightItem(BaseModel):
    """핵심 하이라이트 아이템 모델"""
    
    id: int = Field(..., description="이 하이라이트의 출처 콘텐츠 ID")
    keyword: str = Field(..., description="카테고리를 대표하는 원본 키워드 (원문 언어 유지)")
    highlight: str = Field(..., description="카테고리의 본질을 포착하는 핵심 인사이트 또는 구절 (원문 언어 유지, 번역 금지)")