"""LLM Provider 중립 데이터 모델"""

from dataclasses import dataclass, field
from typing import Any, Optional, Type

from pydantic import BaseModel

from src.core.llm.enums import FinishReason, ResponseFormat


@dataclass
class TokenUsage:
    """토큰 사용량"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Provider 중립 LLM 응답"""
    text: str
    finish_reason: FinishReason
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw_response: Any = None  # 디버깅용 원본 응답
    parsed: Any = None  # 파싱된 Pydantic 객체 (OpenAI parse() 사용 시)


@dataclass
class PersonaConfig:
    """페르소나 설정"""
    name: str
    model_name: str
    temperature: float
    system_instruction: Optional[str] = None
    response_format: ResponseFormat = ResponseFormat.TEXT
    response_schema: Optional[Type[BaseModel]] = None  # Pydantic 모델 클래스
