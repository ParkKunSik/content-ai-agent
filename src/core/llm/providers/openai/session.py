"""OpenAI Session 구현"""

import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

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
        response_schema: Optional[Type[BaseModel]] = None,  # Pydantic 클래스
    ):
        self._client = client
        self._model_name = model_name
        self._temperature = temperature
        self._system_instruction = system_instruction
        self._response_schema = response_schema
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

        # Provider 중립 형식으로 변환 (parse() 사용 시 is_parsed=True)
        return OpenAIResponseMapper.map_response(response, is_parsed=bool(self._response_schema))

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

            # 응답 변환 (parse() 사용 시 is_parsed=True)
            llm_response = OpenAIResponseMapper.map_response(response, is_parsed=bool(self._response_schema))

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
            # Responses API는 developer role 사용
            messages.append({"role": "developer", "content": self._system_instruction})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_chat_messages(self) -> List[Dict[str, str]]:
        """채팅 히스토리를 포함한 메시지 목록을 구성한다."""
        messages = []
        if self._system_instruction:
            # Responses API는 developer role 사용
            messages.append({"role": "developer", "content": self._system_instruction})
        messages.extend(self._chat_history)
        return messages

    def _call_api(self, messages: List[Dict[str, str]]) -> Any:
        """OpenAI Responses API를 호출한다."""
        if self._response_schema:
            # Pydantic 모델로 자동 파싱 (responses.parse)
            return self._client.responses.parse(
                model=self._model_name,
                input=messages,
                temperature=self._temperature,
                text_format=self._response_schema,
            )
        else:
            # 일반 텍스트 응답 (responses.create)
            return self._client.responses.create(
                model=self._model_name,
                input=messages,
                temperature=self._temperature,
            )

    def _log_response_metadata(self, response: Any) -> None:
        """OpenAI Responses API 응답의 저수준 메타데이터를 로깅한다."""
        try:
            # 토큰 사용량 로깅 (Responses API: input_tokens, output_tokens)
            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                total = getattr(usage, "total_tokens", 0)
                if total:
                    logger.debug(f"LLM tokens: {total} (model: {self._model_name})")

            # status 모니터링 (Responses API)
            if hasattr(response, "status") and response.status:
                status = response.status
                if status in ["failed", "incomplete"]:
                    logger.warning(
                        f"LLM status alert: {status} (model: {self._model_name})"
                    )
                else:
                    logger.debug(
                        f"LLM status: {status} (model: {self._model_name})"
                    )

        except Exception as e:
            logger.debug(f"Failed to log response metadata: {e}")
