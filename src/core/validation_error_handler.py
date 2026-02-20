import asyncio
import json
import logging
import random
from typing import Any, Awaitable, Callable, Dict, Generic, Optional, Tuple, TypeVar

from pydantic import BaseModel, ValidationError

from src.core.llm.exceptions import LLMError, RateLimitError
from src.core.llm.models import LLMResponse

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class ValidationErrorHandler(Generic[T]):
    """
    JSON 응답 검증 실패 시 자동 재시도 및 에러 복구를 담당하는 핸들러.
    Provider 중립적으로 설계되어 Vertex AI, OpenAI 등 모든 LLM Provider를 지원한다.
    """

    def __init__(self, max_retries: int = 3, delay_between_retries: float = 1.0):
        self.max_retries = max_retries
        self.delay_between_retries = delay_between_retries

    async def validate_with_retry(
        self,
        response_generator: Callable[[], Awaitable[str]],
        model_class: type[T],
        error_context: str = "validation"
    ) -> T:
        """
        응답 생성 함수를 호출하고 지정된 모델로 검증을 시도한다.
        실패 시 자동으로 재시도한다.

        Args:
            response_generator: 응답을 생성하는 함수 (재시도 시 다시 호출됨)
            model_class: 검증할 Pydantic 모델 클래스
            error_context: 에러 로깅용 컨텍스트

        Returns:
            검증된 모델 인스턴스

        Raises:
            ValidationError: 최대 재시도 횟수 초과 시
        """
        last_error = None
        last_response = None

        for attempt in range(self.max_retries + 1):
            try:
                # 응답 생성
                response_str = await response_generator()
                last_response = response_str

                # JSON 파싱 및 검증
                parsed_data = self._parse_json_response(response_str)
                validated_model = model_class(**parsed_data)

                if attempt > 0:
                    logger.info(f"{error_context} succeeded on attempt {attempt + 1}")

                return validated_model

            except (json.JSONDecodeError, ValidationError, LLMError) as e:
                last_error = e

                if attempt < self.max_retries:
                    # Rate Limit 에러는 Exponential backoff with jitter 적용
                    if isinstance(e, RateLimitError) or self._is_rate_limit_error(e):
                        delay = self._calculate_backoff_delay(attempt)
                        logger.warning(
                            f"{error_context} rate limit hit on attempt {attempt + 1}/{self.max_retries + 1}, waiting {delay:.2f}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        # 일반적인 파싱/검증 오류는 기존 delay 사용
                        logger.warning(
                            f"{error_context} failed on attempt {attempt + 1}/{self.max_retries + 1}: {e}"
                        )
                        await asyncio.sleep(self.delay_between_retries)
                else:
                    logger.error(f"{error_context} failed after {self.max_retries + 1} attempts")
                    break
        
        # 최종 실패 시 상세 에러 정보 로깅
        self._log_final_error(last_error, last_response, error_context)
        
        if isinstance(last_error, json.JSONDecodeError):
            raise ValueError(f"{error_context} failed: JSON parsing error after {self.max_retries + 1} attempts") from last_error
        else:
            raise ValueError(f"{error_context} failed: Validation error after {self.max_retries + 1} attempts") from last_error
    
    def _parse_json_response(self, response_str: str) -> Dict[str, Any]:
        """
        응답 문자열을 정리하고 JSON으로 파싱한다.
        기존 LLMService의 파싱 로직을 통합.
        """
        # 마크다운 코드 블록 제거 및 공백 정리
        cleaned = response_str.strip().replace("```json", "").replace("```", "").strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # 일반적인 JSON 오류 패턴 자동 수정 시도
            cleaned_attempt = self._attempt_json_fixes(cleaned)
            if cleaned_attempt != cleaned:
                try:
                    return json.loads(cleaned_attempt)
                except json.JSONDecodeError:
                    pass
            
            # 수정이 불가능한 경우 원본 에러 발생
            raise e
    
    def _attempt_json_fixes(self, json_str: str) -> str:
        """
        일반적인 JSON 형식 오류를 자동으로 수정 시도한다.
        """
        import re
        
        # 시도 1: Trailing comma 제거
        fixed = re.sub(r',\s*}', '}', json_str)
        fixed = re.sub(r',\s*]', ']', fixed)
        
        # 시도 2: 연속된 공백 정리
        fixed = re.sub(r'\s+', ' ', fixed)
        
        return fixed
    
    def _log_final_error(self, error: Exception, response: Optional[str], context: str):
        """최종 실패 시 상세한 에러 정보를 로깅한다."""
        logger.error(f"Final {context} failure: {type(error).__name__}: {error}")
        
        if response:
            logger.error(f"Last response (first 500 chars): {response[:500]}")
            logger.error(f"Last response (last 500 chars): {response[-500:]}")
            
            # JSON 파싱 에러의 경우 에러 위치 정보 추가
            if isinstance(error, json.JSONDecodeError):
                error_pos = getattr(error, 'pos', 0)
                context_start = max(0, error_pos - 50)
                context_end = min(len(response), error_pos + 50)
                error_context = response[context_start:context_end]
                logger.error(f"JSON error context around position {error_pos}: ...{error_context}...")
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """에러가 Rate Limit 에러인지 확인한다 (Provider 중립)."""
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in ["429", "quota", "rate", "limit", "exhausted"])
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter 계산 (베스트 프랙티스)."""
        # Exponential backoff: 2^attempt seconds
        base_delay = min(2 ** attempt, 60)  # 최대 60초 제한

        # Jitter 추가 (±20% 랜덤 변동)
        jitter = base_delay * 0.2 * (2 * random.random() - 1)  # -20% ~ +20%

        return max(base_delay + jitter, 1.0)  # 최소 1초 보장

    async def validate_with_retry_and_usage(
        self,
        response_generator: Callable[[], Awaitable[Tuple[str, LLMResponse]]],
        model_class: type[T],
        error_context: str = "validation"
    ) -> Tuple[T, LLMResponse]:
        """
        응답 생성 함수를 호출하고 지정된 모델로 검증을 시도한다.
        실패 시 자동으로 재시도한다. LLMResponse도 함께 반환하여 토큰 정보 접근 가능.

        Args:
            response_generator: (text, LLMResponse) 튜플을 생성하는 함수
            model_class: 검증할 Pydantic 모델 클래스
            error_context: 에러 로깅용 컨텍스트

        Returns:
            Tuple[T, LLMResponse]: 검증된 모델 인스턴스와 LLM 응답

        Raises:
            ValidationError: 최대 재시도 횟수 초과 시
        """
        last_error = None
        last_response = None
        last_llm_response: Optional[LLMResponse] = None
        total_input_tokens = 0
        total_output_tokens = 0

        for attempt in range(self.max_retries + 1):
            try:
                # 응답 생성
                response_str, llm_response = await response_generator()
                last_response = response_str
                last_llm_response = llm_response

                # 토큰 누적 (재시도 시에도 합산)
                total_input_tokens += llm_response.usage.prompt_tokens
                total_output_tokens += llm_response.usage.completion_tokens

                # JSON 파싱 및 검증
                parsed_data = self._parse_json_response(response_str)
                validated_model = model_class(**parsed_data)

                if attempt > 0:
                    logger.info(f"{error_context} succeeded on attempt {attempt + 1}")

                # 마지막 성공한 응답에 누적 토큰 정보 반영
                if last_llm_response:
                    last_llm_response.usage.prompt_tokens = total_input_tokens
                    last_llm_response.usage.completion_tokens = total_output_tokens

                return validated_model, last_llm_response

            except (json.JSONDecodeError, ValidationError, LLMError) as e:
                last_error = e

                if attempt < self.max_retries:
                    # Rate Limit 에러는 Exponential backoff with jitter 적용
                    if isinstance(e, RateLimitError) or self._is_rate_limit_error(e):
                        delay = self._calculate_backoff_delay(attempt)
                        logger.warning(
                            f"{error_context} rate limit hit on attempt {attempt + 1}/{self.max_retries + 1}, waiting {delay:.2f}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        # 일반적인 파싱/검증 오류는 기존 delay 사용
                        logger.warning(
                            f"{error_context} failed on attempt {attempt + 1}/{self.max_retries + 1}: {e}"
                        )
                        await asyncio.sleep(self.delay_between_retries)
                else:
                    logger.error(f"{error_context} failed after {self.max_retries + 1} attempts")
                    break

        # 최종 실패 시 상세 에러 정보 로깅
        self._log_final_error(last_error, last_response, error_context)

        if isinstance(last_error, json.JSONDecodeError):
            raise ValueError(f"{error_context} failed: JSON parsing error after {self.max_retries + 1} attempts") from last_error
        else:
            raise ValueError(f"{error_context} failed: Validation error after {self.max_retries + 1} attempts") from last_error