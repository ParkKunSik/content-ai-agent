"""Vertex AI Provider 설정"""

from src.core.config.providers.base import ProviderSettings


class VertexAISettings(ProviderSettings):
    """
    Vertex AI 설정

    인증: GCP 서비스 계정 (GOOGLE_APPLICATION_CREDENTIALS)

    모델 가이드 (2026-01 기준):
    - gemini-2.5-pro: 고급 추론, 최대 65,535 출력 토큰
    - gemini-2.5-flash: 빠른 처리, 최대 65,535 출력 토큰
    - gemini-3-pro-preview: 최신, 32,768 출력 토큰 (제약)
    - gemini-3-flash-preview: 최신, 32,768 출력 토큰 (제약)
    """
    MODEL_ADVANCED: str = "gemini-2.5-pro"
    MODEL_STANDARD: str = "gemini-2.5-flash"
