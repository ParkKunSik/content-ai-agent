"""Provider 설정 기본 클래스"""

from pydantic import BaseModel


class ProviderSettings(BaseModel):
    """
    Provider 설정 기본 클래스

    MODEL_ADVANCED: 고성능/추론 강화 모델 (gemini-2.5-pro, gpt-4o)
    MODEL_STANDARD: 빠른 응답/경량 모델 (gemini-2.5-flash, gpt-4o-mini)
    """
    MODEL_ADVANCED: str
    MODEL_STANDARD: str
