"""Viewer용 Enum 정의"""

from enum import Enum


class ContentType(str, Enum):
    """콘텐츠 타입 (외부 API용 단순화 버전)"""

    SUPPORT = "SUPPORT"
    SUGGESTION = "SUGGESTION"
    REVIEW = "REVIEW"
    SATISFACTION = "SATISFACTION"

    @property
    def description(self) -> str:
        """한글 설명"""
        descriptions = {
            "SUPPORT": "응원",
            "SUGGESTION": "의견",
            "REVIEW": "체험리뷰",
            "SATISFACTION": "만족도",
        }
        return descriptions.get(self.value, self.value)
