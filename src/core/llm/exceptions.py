"""LLM Provider 관련 예외 정의"""


class LLMError(Exception):
    """LLM 관련 기본 예외"""

    def __init__(self, message: str, provider: str = None, original_error: Exception = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


class RateLimitError(LLMError):
    """API Rate Limit 초과"""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        super().__init__(message, **kwargs)


class SafetyError(LLMError):
    """안전 필터에 의한 차단"""

    def __init__(self, message: str = "Content blocked by safety filter", **kwargs):
        super().__init__(message, **kwargs)


class ContentFilterError(LLMError):
    """콘텐츠 필터에 의한 차단"""

    def __init__(self, message: str = "Content blocked by content filter", **kwargs):
        super().__init__(message, **kwargs)


class MaxTokensError(LLMError):
    """최대 토큰 제한 도달"""

    def __init__(self, message: str = "Maximum token limit reached", **kwargs):
        super().__init__(message, **kwargs)


class ProviderNotFoundError(LLMError):
    """Provider를 찾을 수 없음"""

    def __init__(self, provider: str):
        super().__init__(f"Provider not found: {provider}", provider=provider)


class ProviderNotInitializedError(LLMError):
    """Provider가 초기화되지 않음"""

    def __init__(self, provider: str):
        super().__init__(f"Provider not initialized: {provider}", provider=provider)
