"""LLM Provider Factory 추상 클래스"""

from abc import ABC, abstractmethod

from src.core.llm.base.session import LLMProviderSession
from src.core.llm.models import PersonaConfig


class LLMProviderFactory(ABC):
    """
    LLM Provider Factory 추상 기본 클래스.
    모든 Provider Factory는 이 클래스를 상속받아 구현해야 한다.
    """

    @classmethod
    @abstractmethod
    def initialize(cls) -> None:
        """
        Provider를 초기화한다.
        SDK 클라이언트 생성, 인증 처리 등을 수행한다.
        """
        ...

    @classmethod
    @abstractmethod
    def start_session(
        cls,
        persona_config: PersonaConfig,
    ) -> LLMProviderSession:
        """
        새로운 LLM 세션을 시작한다.

        Args:
            persona_config: 페르소나 설정 (모델명, 온도, response_schema 등)

        Returns:
            LLMProviderSession: Provider 세션 인스턴스
        """
        ...

    @classmethod
    @abstractmethod
    def count_tokens(cls, text: str, model_name: str) -> int:
        """
        텍스트의 토큰 수를 계산한다.

        Args:
            text: 토큰 수를 계산할 텍스트
            model_name: 토큰화에 사용할 모델명

        Returns:
            int: 토큰 수
        """
        ...

    @classmethod
    @abstractmethod
    def get_provider_name(cls) -> str:
        """Provider 이름을 반환한다."""
        ...
