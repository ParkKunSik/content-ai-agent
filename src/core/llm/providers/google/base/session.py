"""Google GenAI 공통 Session 기반 클래스"""

import logging
from abc import ABC
from typing import Any, Dict, List, TYPE_CHECKING

from src.core.llm.base.session import LLMProviderSession
from src.core.llm.models import LLMResponse
from src.core.llm.providers.google.base.response_mapper import GoogleGenAIResponseMapper

if TYPE_CHECKING:
    import google.genai as genai
    from google.genai import types

logger = logging.getLogger(__name__)


class GoogleGenAIBaseSession(LLMProviderSession, ABC):
    """
    Google GenAI (google-genai SDK) 공통 기반 세션.
    Vertex AI와 Gemini API가 공유하는 로직을 포함한다.
    """

    def __init__(
        self,
        client: "genai.Client",
        model_name: str,
        config: "types.GenerateContentConfig"
    ):
        self._client = client
        self._model_name = model_name
        self._config = config
        self._chat_session = None
        self._message_history: List[Dict[str, Any]] = []

    def generate_content(self, prompt: str) -> LLMResponse:
        """
        프롬프트를 입력받아 콘텐츠를 생성한다 (stateless 모드).

        Args:
            prompt: 입력 프롬프트

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=self._config
        )

        # 저수준 로깅
        self._log_response_metadata(response)

        # Provider 중립 형식으로 변환
        return GoogleGenAIResponseMapper.map_response(response)

    async def start_chat_session(self) -> None:
        """
        상태 유지형 채팅 세션을 시작한다.
        한 번만 호출되어야 하며, 이후 send_message()를 사용한다.
        """
        if self._chat_session is not None:
            logger.warning("Chat session already started, ignoring duplicate call")
            return

        try:
            self._chat_session = self._client.chats.create(
                model=self._model_name,
                config=self._config
            )
            logger.debug(f"Chat session started successfully with model: {self._model_name}")
        except Exception as e:
            logger.error(f"Failed to start chat session: {e}")
            raise RuntimeError("Failed to initialize chat session") from e

    async def send_message(self, message: str) -> LLMResponse:
        """
        채팅 세션에 메시지를 전송하고 응답을 받는다.
        start_chat_session()이 먼저 호출되어야 한다.

        Args:
            message: 전송할 메시지

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        if self._chat_session is None:
            raise RuntimeError("Chat session not started. Call start_chat_session() first.")

        try:
            response = self._chat_session.send_message(message)

            # 저수준 로깅
            self._log_response_metadata(response)

            # 히스토리 저장
            llm_response = GoogleGenAIResponseMapper.map_response(response)
            self._message_history.append({
                "role": "user",
                "content": message,
                "timestamp": None
            })
            self._message_history.append({
                "role": "model",
                "content": llm_response.text,
                "timestamp": None
            })

            return llm_response
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise RuntimeError("Failed to send message to chat session") from e

    def get_message_history(self) -> List[Dict[str, Any]]:
        """채팅 세션의 메시지 히스토리를 반환한다."""
        return self._message_history.copy()

    def is_chat_session_active(self) -> bool:
        """채팅 세션이 활성 상태인지 확인한다."""
        return self._chat_session is not None

    def reset_chat_session(self) -> None:
        """채팅 세션과 히스토리를 초기화한다."""
        self._chat_session = None
        self._message_history.clear()
        logger.debug("Chat session and history reset")

    def _log_response_metadata(self, response: "types.GenerateContentResponse") -> None:
        """GenerateContentResponse의 저수준 메타데이터를 로깅한다."""
        try:
            from google.genai import types

            # 토큰 사용량 로깅 (비용 모니터링)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                if hasattr(usage, "total_token_count") and usage.total_token_count:
                    logger.debug(f"LLM tokens: {usage.total_token_count} (model: {self._model_name})")

            # finish_reason 모니터링 (SDK enum 직접 사용)
            if hasattr(response, "candidates") and response.candidates:
                for i, candidate in enumerate(response.candidates):
                    if hasattr(candidate, "finish_reason") and candidate.finish_reason:
                        finish_reason = candidate.finish_reason

                        # 문제 있는 finish_reason 경고
                        problematic_reasons = [
                            types.FinishReason.MAX_TOKENS,
                            types.FinishReason.SAFETY,
                            types.FinishReason.PROHIBITED_CONTENT,
                            types.FinishReason.BLOCKLIST,
                            types.FinishReason.SPII,
                            types.FinishReason.RECITATION,
                        ]

                        if finish_reason in problematic_reasons:
                            logger.warning(
                                f"LLM finish_reason alert: {finish_reason} (model: {self._model_name}, candidate: {i})"
                            )
                        else:
                            logger.debug(
                                f"LLM finish_reason: {finish_reason} (model: {self._model_name}, candidate: {i})"
                            )

        except Exception as e:
            # 로깅 실패는 조용히 처리 (응답 생성에 영향주지 않음)
            logger.debug(f"Failed to log response metadata: {e}")
