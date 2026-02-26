"""Vertex AI Session 구현"""

from src.core.llm.providers.google.base.session import GoogleGenAIBaseSession


class VertexAISession(GoogleGenAIBaseSession):
    """
    Vertex AI (google-genai SDK, vertexai=True) 기반 세션.

    GoogleGenAIBaseSession을 상속받아 모든 공통 기능을 재사용한다.
    Vertex AI 전용 기능이 필요한 경우 여기에 추가한다.
    """
    pass
