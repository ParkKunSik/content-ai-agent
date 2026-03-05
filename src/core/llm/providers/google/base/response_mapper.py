"""Google GenAI 응답을 Provider 중립 형식으로 변환"""

import logging
from typing import TYPE_CHECKING

from src.core.llm.enums import FinishReason
from src.core.llm.models import LLMResponse, TokenUsage

if TYPE_CHECKING:
    from google.genai import types

logger = logging.getLogger(__name__)


class GoogleGenAIResponseMapper:
    """
    Google GenAI (google-genai SDK) 응답을 LLMResponse로 변환.
    Vertex AI와 Gemini API 모두에서 공유된다.
    """

    # Google FinishReason → Provider 중립 FinishReason 매핑
    FINISH_REASON_MAP = {
        "STOP": FinishReason.STOP,
        "MAX_TOKENS": FinishReason.MAX_TOKENS,
        "SAFETY": FinishReason.SAFETY,
        "PROHIBITED_CONTENT": FinishReason.CONTENT_FILTER,
        "BLOCKLIST": FinishReason.CONTENT_FILTER,
        "SPII": FinishReason.CONTENT_FILTER,
        "RECITATION": FinishReason.RECITATION,
    }

    @classmethod
    def map_response(cls, response: "types.GenerateContentResponse") -> LLMResponse:
        """
        Google GenAI 응답을 LLMResponse로 변환한다.

        Args:
            response: Google GenAI 응답 객체

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        # 텍스트 추출
        text = response.text if hasattr(response, "text") else ""

        # finish_reason 매핑
        finish_reason = cls._extract_finish_reason(response)

        # 토큰 사용량 추출
        usage = cls._extract_usage(response)

        return LLMResponse(
            text=text,
            finish_reason=finish_reason,
            usage=usage,
            raw_response=response,
        )

    @classmethod
    def _extract_finish_reason(cls, response: "types.GenerateContentResponse") -> FinishReason:
        """응답에서 finish_reason을 추출하고 매핑한다."""
        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason") and candidate.finish_reason:
                    reason_name = str(candidate.finish_reason.name) if hasattr(candidate.finish_reason, "name") else str(candidate.finish_reason)
                    return cls.FINISH_REASON_MAP.get(reason_name, FinishReason.OTHER)
        except Exception as e:
            logger.debug(f"Failed to extract finish_reason: {e}")

        return FinishReason.OTHER

    @classmethod
    def _extract_usage(cls, response: "types.GenerateContentResponse") -> TokenUsage:
        """응답에서 토큰 사용량을 추출한다.

        Note:
            Gemini 2.5 Pro는 thinking이 기본 활성화되어 있으며,
            thinking_tokens는 output 요금으로 별도 과금됩니다.
            - Gemini API: candidates_token_count에 thinking tokens 포함
            - Vertex AI: candidates_token_count에 thinking tokens 미포함 (별도 필드)
        """
        try:
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                thinking_tokens = getattr(usage, "thoughts_token_count", 0) or 0

                if thinking_tokens > 0:
                    logger.debug(f"Thinking tokens used: {thinking_tokens}")

                return TokenUsage(
                    prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                    completion_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                    total_tokens=getattr(usage, "total_token_count", 0) or 0,
                    thinking_tokens=thinking_tokens,
                )
        except Exception as e:
            logger.debug(f"Failed to extract usage: {e}")

        return TokenUsage()
