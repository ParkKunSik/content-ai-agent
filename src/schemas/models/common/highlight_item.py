from pydantic import BaseModel, Field


class HighlightItem(BaseModel):
    """핵심 하이라이트 아이템 모델"""
    
    id: int = Field(..., description="참고한 콘텐츠 ID")
    keyword: str = Field(..., description="하이라이트의 근거가 되는 원본 키워드")
    highlight: str = Field(..., description="추출된 핵심 문장 또는 요약")