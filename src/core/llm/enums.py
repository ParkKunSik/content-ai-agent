"""LLM Provider 관련 Enum 정의"""

from enum import Enum
from typing import Callable, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.llm.base.factory import LLMProviderFactory


class ProviderType(str, Enum):
    """
    LLM Provider 타입.

    각 Provider는 Factory 로더 lambda를 포함하며,
    get_factory() 메서드를 통해 동적으로 로드할 수 있다.
    """

    VERTEX_AI = (
        lambda: __import__(
            "src.core.llm.providers.google.vertexai.factory",
            fromlist=["VertexAIProviderFactory"]
        ).VertexAIProviderFactory,
    )
    GEMINI_API = (
        lambda: __import__(
            "src.core.llm.providers.google.gemini.factory",
            fromlist=["GeminiAPIProviderFactory"]
        ).GeminiAPIProviderFactory,
    )
    OPENAI = (
        lambda: __import__(
            "src.core.llm.providers.openai.factory",
            fromlist=["OpenAIProviderFactory"]
        ).OpenAIProviderFactory,
    )

    def __init__(self, factory_loader: Callable[[], Type["LLMProviderFactory"]]):
        self._value_ = self.name
        self._factory_loader = factory_loader

    @classmethod
    def _missing_(cls, value):
        """문자열 값으로 멤버를 찾는다 (pydantic 호환)."""
        for member in cls:
            if member.name == value:
                return member
        return None

    def get_factory(self) -> Optional[Type["LLMProviderFactory"]]:
        """
        Factory 클래스를 동적으로 로드한다.

        Returns:
            LLMProviderFactory 구현체 클래스. 로드 실패 시 None.
        """
        try:
            return self._factory_loader()
        except ImportError:
            return None


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
