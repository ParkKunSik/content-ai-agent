"""OpenAI 응답을 Provider 중립 형식으로 변환"""

import logging
from typing import Any

from src.core.llm.enums import FinishReason
from src.core.llm.models import LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


class OpenAIResponseMapper:
    """OpenAI Responses API 응답을 LLMResponse로 매핑"""

    # OpenAI status → FinishReason 매핑 (Responses API)
    _STATUS_MAP = {
        "completed": FinishReason.STOP,
        "failed": FinishReason.OTHER,
        "incomplete": FinishReason.MAX_TOKENS,
    }

    @classmethod
    def map_response(cls, response: Any, is_parsed: bool = False) -> LLMResponse:
        """
        OpenAI Responses API 응답을 LLMResponse로 변환한다.

        Args:
            response: OpenAI Responses API 응답 객체
            is_parsed: responses.parse() 사용 여부

        Returns:
            LLMResponse: Provider 중립 응답 객체
        """
        # parsed 객체 추출 (parse() 사용 시)
        parsed = None
        if is_parsed:
            parsed = cls._extract_parsed(response)

        # 텍스트 추출
        if parsed:
            text = parsed.model_dump_json()
        else:
            text = cls._extract_text(response)

        # status → finish_reason 매핑
        finish_reason = cls._map_status(response)

        # 토큰 사용량 추출
        usage = cls._extract_usage(response)

        return LLMResponse(
            text=text,
            finish_reason=finish_reason,
            usage=usage,
            raw_response=response,
            parsed=parsed,
        )

    @classmethod
    def _extract_text(cls, response: Any) -> str:
        """Responses API 응답에서 텍스트를 추출한다."""
        try:
            # Responses API: response.output[].content[].text
            if hasattr(response, "output") and response.output:
                for output_item in response.output:
                    if getattr(output_item, "type", None) == "message":
                        content = getattr(output_item, "content", [])
                        for content_item in content:
                            if getattr(content_item, "type", None) == "output_text":
                                return getattr(content_item, "text", "") or ""
            # output_text 속성으로 직접 접근 시도
            if hasattr(response, "output_text") and response.output_text:
                return response.output_text
        except Exception as e:
            logger.warning(f"Failed to extract text from Responses API: {e}")
        return ""

    @classmethod
    def _map_status(cls, response: Any) -> FinishReason:
        """Responses API status를 FinishReason으로 매핑한다."""
        try:
            if hasattr(response, "status") and response.status:
                return cls._STATUS_MAP.get(response.status, FinishReason.OTHER)
        except Exception as e:
            logger.debug(f"Failed to map status: {e}")
        return FinishReason.OTHER

    @classmethod
    def _extract_usage(cls, response: Any) -> TokenUsage:
        """응답에서 토큰 사용량을 추출한다."""
        try:
            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                return TokenUsage(
                    prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "output_tokens", 0) or 0,
                    total_tokens=getattr(usage, "total_tokens", 0) or 0,
                )
        except Exception as e:
            logger.debug(f"Failed to extract usage: {e}")
        return TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    @classmethod
    def _extract_parsed(cls, response: Any) -> Any:
        """Responses API 응답에서 파싱된 Pydantic 객체를 추출한다."""
        try:
            # Responses API: response.output_parsed
            if hasattr(response, "output_parsed") and response.output_parsed:
                return response.output_parsed
        except Exception as e:
            logger.warning(f"Failed to extract parsed object: {e}")
        return None
