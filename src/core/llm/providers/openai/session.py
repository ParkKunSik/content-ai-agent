"""OpenAI Session 구현"""

import logging
from typing import Any, Dict, List, Optional

from src.core.llm.base.session import LLMProviderSession
from src.core.llm.models import LLMResponse
from src.core.llm.providers.openai.response_mapper import OpenAIResponseMapper

logger = logging.getLogger(__name__)


class OpenAISession(LLMProviderSession):
    """
    OpenAI API 기반 세션.
    LLMProviderSession ABC를 구현하며,
    stateless 및 stateful(chat session) 모드를 모두 지원한다.
    """

    def __init__(
        self,
        client: Any,  # openai.OpenAI
        model_name: str,
        temperature: float,
        system_instruction: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ):
        self._client = client
        self._model_name = model_name
        self._temperature = temperature
        self._system_instruction = system_instruction
        self._response_format = response_format
        self._chat_history: List[Dict[str, str]] = []
        self._chat_session_active = False

    def generate_content(self, prompt: str) -> LLMResponse:
        """
        프롬프트를 입력받아 콘텐츠를 생성한다 (stateless 모드).

        Args:
            prompt: 입력 프롬프트

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        messages = self._build_messages(prompt)

        response = self._call_api(messages)

        # 저수준 로깅
        self._log_response_metadata(response)

        # Provider 중립 형식으로 변환
        return OpenAIResponseMapper.map_response(response)

    async def start_chat_session(self) -> None:
        """
        상태 유지형 채팅 세션을 시작한다.
        한 번만 호출되어야 하며, 이후 send_message()를 사용한다.
        """
        if self._chat_session_active:
            logger.warning("Chat session already started, ignoring duplicate call")
            return

        self._chat_history.clear()
        self._chat_session_active = True
        logger.debug(f"Chat session started with model: {self._model_name}")

    async def send_message(self, message: str) -> LLMResponse:
        """
        채팅 세션에 메시지를 전송하고 응답을 받는다.
        start_chat_session()이 먼저 호출되어야 한다.

        Args:
            message: 전송할 메시지

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        if not self._chat_session_active:
            raise RuntimeError("Chat session not started. Call start_chat_session() first.")

        try:
            # 현재 메시지를 히스토리에 추가
            self._chat_history.append({"role": "user", "content": message})

            # 전체 히스토리로 API 호출
            messages = self._build_chat_messages()
            response = self._call_api(messages)

            # 저수준 로깅
            self._log_response_metadata(response)

            # 응답 변환
            llm_response = OpenAIResponseMapper.map_response(response)

            # 응답을 히스토리에 추가
            self._chat_history.append({"role": "assistant", "content": llm_response.text})

            return llm_response
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise RuntimeError("Failed to send message to chat session") from e

    def get_message_history(self) -> List[Dict[str, Any]]:
        """채팅 세션의 메시지 히스토리를 반환한다."""
        return [
            {"role": msg["role"], "content": msg["content"], "timestamp": None}
            for msg in self._chat_history
        ]

    def is_chat_session_active(self) -> bool:
        """채팅 세션이 활성 상태인지 확인한다."""
        return self._chat_session_active

    def reset_chat_session(self) -> None:
        """채팅 세션과 히스토리를 초기화한다."""
        self._chat_history.clear()
        self._chat_session_active = False
        logger.debug("Chat session and history reset")

    def _build_messages(self, prompt: str) -> List[Dict[str, str]]:
        """단일 요청용 메시지 목록을 구성한다."""
        messages = []
        if self._system_instruction:
            # OpenAI에 최적화된 강화 지시문 추가
            enhanced_instruction = self._enhance_system_instruction(self._system_instruction)
            messages.append({"role": "system", "content": enhanced_instruction})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_chat_messages(self) -> List[Dict[str, str]]:
        """채팅 히스토리를 포함한 메시지 목록을 구성한다."""
        messages = []
        if self._system_instruction:
            enhanced_instruction = self._enhance_system_instruction(self._system_instruction)
            messages.append({"role": "system", "content": enhanced_instruction})
        messages.extend(self._chat_history)
        return messages

    def _enhance_system_instruction(self, instruction: str) -> str:
        """OpenAI 모델에 최적화된 강화 지시문을 생성한다."""
        return f"""{instruction}

    [CRITICAL INSTRUCTIONS]
    - Follow the system instructions EXACTLY as specified above.
    - Output MUST be valid JSON matching the required schema precisely.
    - Be thorough, detailed, and comprehensive in your analysis.
    - Do NOT skip or omit any required fields in the response."""

    def _call_api(self, messages: List[Dict[str, str]]) -> Any:
        """OpenAI API를 호출한다."""
        kwargs = {
            "model": self._model_name,
            "messages": messages,
            "temperature": self._temperature,
        }

        # JSON 응답 형식 설정
        if self._response_format:
            kwargs["response_format"] = self._response_format

        return self._client.chat.completions.create(**kwargs)

    def _log_response_metadata(self, response: Any) -> None:
        """OpenAI 응답의 저수준 메타데이터를 로깅한다."""
        try:
            # 토큰 사용량 로깅
            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                total = getattr(usage, "total_tokens", 0)
                if total:
                    logger.debug(f"LLM tokens: {total} (model: {self._model_name})")

            # finish_reason 모니터링
            if hasattr(response, "choices") and response.choices:
                for i, choice in enumerate(response.choices):
                    finish_reason = getattr(choice, "finish_reason", None)
                    if finish_reason:
                        # 문제 있는 finish_reason 경고
                        if finish_reason in ["length", "content_filter"]:
                            logger.warning(
                                f"LLM finish_reason alert: {finish_reason} "
                                f"(model: {self._model_name}, choice: {i})"
                            )
                        else:
                            logger.debug(
                                f"LLM finish_reason: {finish_reason} "
                                f"(model: {self._model_name}, choice: {i})"
                            )

        except Exception as e:
            logger.debug(f"Failed to log response metadata: {e}")
