"""LLM Provider Session 추상 클래스"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.core.llm.models import LLMResponse


class LLMProviderSession(ABC):
    """
    LLM Provider Session 추상 기본 클래스.
    모든 Provider Session은 이 클래스를 상속받아 구현해야 한다.
    """

    @abstractmethod
    def generate_content(self, prompt: str) -> LLMResponse:
        """
        프롬프트를 입력받아 콘텐츠를 생성한다 (stateless 모드).

        Args:
            prompt: 입력 프롬프트

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        ...

    @abstractmethod
    async def start_chat_session(self) -> None:
        """
        상태 유지형 채팅 세션을 시작한다.
        한 번만 호출되어야 하며, 이후 send_message()를 사용한다.
        """
        ...

    @abstractmethod
    async def send_message(self, message: str) -> LLMResponse:
        """
        채팅 세션에 메시지를 전송하고 응답을 받는다.
        start_chat_session()이 먼저 호출되어야 한다.

        Args:
            message: 전송할 메시지

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        ...

    @abstractmethod
    def get_message_history(self) -> List[Dict[str, Any]]:
        """채팅 세션의 메시지 히스토리를 반환한다."""
        ...

    @abstractmethod
    def is_chat_session_active(self) -> bool:
        """채팅 세션이 활성 상태인지 확인한다."""
        ...

    @abstractmethod
    def reset_chat_session(self) -> None:
        """채팅 세션과 히스토리를 초기화한다."""
        ...
