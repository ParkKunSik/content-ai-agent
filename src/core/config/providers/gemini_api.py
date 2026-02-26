"""Gemini API Provider 설정"""

from typing import Optional
from src.core.config.providers.base import ProviderSettings


class GeminiAPISettings(ProviderSettings):
    """
    Gemini API 설정

    인증: API Key (https://aistudio.google.com/)
    SDK: google-genai (Vertex AI와 동일)

    Vertex AI와 동일한 모델 사용 가능:
    - gemini-2.5-pro: 고급 추론
    - gemini-2.5-flash: 빠른 처리
    """
    API_KEY: Optional[str] = None
    MODEL_ADVANCED: str = "gemini-2.5-pro"
    MODEL_STANDARD: str = "gemini-2.5-flash"
