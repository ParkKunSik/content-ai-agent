"""LLM Provider 관련 Enum 정의"""

from enum import Enum


class ProviderType(str, Enum):
    """LLM Provider 타입"""
    VERTEX_AI = "VERTEX_AI"      # Google Vertex AI (GCP 서비스 계정 인증)
    # GEMINI = "GEMINI"          # Google Gemini API (API Key 인증, 향후 구현)
    OPENAI = "OPENAI"            # OpenAI API


class FinishReason(str, Enum):
    """LLM 응답 종료 사유 (Provider 중립)"""
    STOP = "STOP"                    # 정상 종료
    MAX_TOKENS = "MAX_TOKENS"        # 토큰 제한 도달
    SAFETY = "SAFETY"                # 안전 필터
    CONTENT_FILTER = "CONTENT_FILTER"  # 콘텐츠 필터
    RECITATION = "RECITATION"        # 인용 감지
    OTHER = "OTHER"                  # 기타


class ResponseFormat(str, Enum):
    """LLM 응답 형식"""
    TEXT = "TEXT"
    JSON = "JSON"
