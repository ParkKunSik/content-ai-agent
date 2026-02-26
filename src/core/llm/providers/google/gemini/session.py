"""Gemini API Session 구현"""

from src.core.llm.providers.google.base.session import GoogleGenAIBaseSession


class GeminiAPISession(GoogleGenAIBaseSession):
    """
    Gemini API (google-genai SDK, API Key 방식) 기반 세션.

    GoogleGenAIBaseSession을 상속받아 모든 공통 기능을 재사용한다.
    Gemini API 전용 기능이 필요한 경우 여기에 추가한다.
    """
    pass
