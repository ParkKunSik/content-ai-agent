"""
[Deprecated] 하위 호환성을 위한 래퍼 모듈.
새 코드에서는 src.core.llm.providers.google.vertexai.session을 사용하세요.
"""

from src.core.llm.providers.google.vertexai.session import AsyncGenAISession

__all__ = ["AsyncGenAISession"]
