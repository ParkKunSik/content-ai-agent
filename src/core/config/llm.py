"""LLM 생성 관련 설정"""

from pydantic import BaseModel


class LLMGenerationSettings(BaseModel):
    """
    LLM 생성 설정

    토큰 제한 가이드:
    - Gemini 2.5 Pro/Flash: 입력 1M, 출력 65,535 토큰
    - Gemini 3.0 Preview: 출력 32,768 토큰 (실제 제약)
    - GPT-4o: Context 128K, Output 16K
    - GPT-4.1: Context 1M, Output 32K
    """
    MAX_OUTPUT_TOKENS: int = 65000
