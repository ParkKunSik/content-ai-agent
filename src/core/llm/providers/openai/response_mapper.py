"""OpenAI 응답을 Provider 중립 형식으로 변환"""

import logging
from typing import Any

from src.core.llm.enums import FinishReason
from src.core.llm.models import LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


class OpenAIResponseMapper:
    """OpenAI 응답을 LLMResponse로 매핑"""

    # OpenAI finish_reason → FinishReason 매핑
    _FINISH_REASON_MAP = {
        "stop": FinishReason.STOP,
        "length": FinishReason.MAX_TOKENS,
        "content_filter": FinishReason.CONTENT_FILTER,
        "tool_calls": FinishReason.STOP,
        "function_call": FinishReason.STOP,
    }

    @classmethod
    def map_response(cls, response: Any) -> LLMResponse:
        """
        OpenAI ChatCompletion 응답을 LLMResponse로 변환한다.

        Args:
            response: OpenAI ChatCompletion 응답 객체

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        # 텍스트 추출
        text = cls._extract_text(response)

        # finish_reason 매핑
        finish_reason = cls._map_finish_reason(response)

        # 토큰 사용량 추출
        usage = cls._extract_usage(response)

        return LLMResponse(
            text=text,
            finish_reason=finish_reason,
            usage=usage,
            raw_response=response,
        )

    @classmethod
    def _extract_text(cls, response: Any) -> str:
        """응답에서 텍스트를 추출한다."""
        try:
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message") and choice.message:
                    return choice.message.content or ""
        except Exception as e:
            logger.warning(f"Failed to extract text from OpenAI response: {e}")
        return ""

    @classmethod
    def _map_finish_reason(cls, response: Any) -> FinishReason:
        """OpenAI finish_reason을 FinishReason으로 매핑한다."""
        try:
            if hasattr(response, "choices") and response.choices:
                raw_reason = response.choices[0].finish_reason
                if raw_reason:
                    return cls._FINISH_REASON_MAP.get(raw_reason, FinishReason.OTHER)
        except Exception as e:
            logger.debug(f"Failed to map finish_reason: {e}")
        return FinishReason.OTHER

    @classmethod
    def _extract_usage(cls, response: Any) -> TokenUsage:
        """응답에서 토큰 사용량을 추출한다."""
        try:
            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                return TokenUsage(
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    total_tokens=getattr(usage, "total_tokens", 0) or 0,
                )
        except Exception as e:
            logger.debug(f"Failed to extract usage: {e}")
        return TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
