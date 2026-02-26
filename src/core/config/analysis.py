"""분석 관련 설정"""

from pydantic import BaseModel


class AnalysisSettings(BaseModel):
    """콘텐츠 분석 설정"""
    MAX_MAIN_SUMMARY_CHARS: int = 300
    MAX_CATEGORY_SUMMARY_CHARS: int = 50
    MAX_INSIGHT_ITEM_CHARS_ANALYSIS: int = 50
    MAX_INSIGHT_ITEM_CHARS_REFINE: int = 30
    STRICT_VALIDATION: bool = False
