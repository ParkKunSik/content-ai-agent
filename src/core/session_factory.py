"""
[Deprecated] 하위 호환성을 위한 래퍼 모듈.
새 코드에서는 src.core.llm.providers.google.vertexai.factory를 사용하세요.
"""

from src.core.llm.providers.google.vertexai.factory import SessionFactory

__all__ = ["SessionFactory"]
