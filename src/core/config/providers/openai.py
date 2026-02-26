"""OpenAI Provider 설정"""

from typing import Optional
from src.core.config.providers.base import ProviderSettings


class OpenAISettings(ProviderSettings):
    """
    OpenAI 설정

    모델 가이드 (2026-02 기준):

    [temperature 지원 모델]
    - gpt-4o: 멀티모달, 128K context, $2.50/$10.00 per 1M tokens
    - gpt-4o-mini: 경제적, 128K context, $0.15/$0.60 per 1M tokens
    - gpt-4.1: 대용량 context 1M, $2.00/$8.00 per 1M tokens
    - gpt-4.1-mini / gpt-4.1-nano: 1M context, 경제적

    [temperature 미지원 모델 - Reasoning]
    - gpt-5 / gpt-5-mini / gpt-5-nano: 400k context, reasoning 내장
    - o1 / o1-mini / o1-preview: 초기 reasoning
    - o3 / o3-mini / o3-pro: 고급 reasoning
    - o4-mini: fast reasoning, math/coding 최적화
    [주의] temperature, top_p 등 샘플링 파라미터 사용 불가
    """
    API_KEY: Optional[str] = None
    ORG_ID: Optional[str] = None
    MODEL_ADVANCED: str = "gpt-4o"
    MODEL_STANDARD: str = "gpt-4o-mini"
