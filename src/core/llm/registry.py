"""LLM Provider Registry"""

import logging
from typing import Dict, Optional, Type

from src.core.llm.base.factory import LLMProviderFactory
from src.core.llm.base.session import LLMProviderSession
from src.core.llm.enums import ProviderType
from src.core.llm.exceptions import ProviderNotFoundError, ProviderNotInitializedError
from src.core.llm.models import PersonaConfig

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    LLM Provider Registry.
    Provider 팩토리를 등록하고 관리한다.
    """

    _factories: Dict[ProviderType, Type[LLMProviderFactory]] = {}
    _initialized: Dict[ProviderType, bool] = {}
    _current_provider: Optional[ProviderType] = None

    @classmethod
    def register(cls, provider_type: ProviderType, factory: Type[LLMProviderFactory]) -> None:
        """
        Provider 팩토리를 등록한다.

        Args:
            provider_type: Provider 타입
            factory: LLMProviderFactory 구현체
        """
        cls._factories[provider_type] = factory
        cls._initialized[provider_type] = False
        logger.debug(f"Registered provider: {provider_type.value}")

    @classmethod
    def initialize(cls, provider_type: ProviderType) -> None:
        """
        특정 Provider를 초기화한다.

        Args:
            provider_type: 초기화할 Provider 타입
        """
        if provider_type not in cls._factories:
            raise ProviderNotFoundError(provider_type.value)

        factory = cls._factories[provider_type]
        factory.initialize()
        cls._initialized[provider_type] = True
        cls._current_provider = provider_type
        logger.info(f"Initialized provider: {provider_type.value}")

    @classmethod
    def get_factory(cls, provider_type: Optional[ProviderType] = None) -> Type[LLMProviderFactory]:
        """
        Provider 팩토리를 반환한다.

        Args:
            provider_type: Provider 타입 (None이면 현재 Provider 사용)

        Returns:
            LLMProviderFactory 구현체
        """
        target_provider = provider_type or cls._current_provider

        if target_provider is None:
            raise ProviderNotInitializedError("No provider initialized")

        if target_provider not in cls._factories:
            raise ProviderNotFoundError(target_provider.value)

        if not cls._initialized.get(target_provider, False):
            raise ProviderNotInitializedError(target_provider.value)

        return cls._factories[target_provider]

    @classmethod
    def start_session(
        cls,
        persona_config: PersonaConfig,
        provider_type: Optional[ProviderType] = None,
    ) -> LLMProviderSession:
        """
        LLM 세션을 시작한다.

        Args:
            persona_config: 페르소나 설정 (모델명, 온도, response_schema 등)
            provider_type: Provider 타입 (None이면 현재 Provider 사용)

        Returns:
            LLMProviderSession 인스턴스
        """
        factory = cls.get_factory(provider_type)
        return factory.start_session(persona_config)

    @classmethod
    def count_tokens(
        cls,
        text: str,
        model_name: str,
        provider_type: Optional[ProviderType] = None,
    ) -> int:
        """
        텍스트의 토큰 수를 계산한다.

        Args:
            text: 토큰 수를 계산할 텍스트
            model_name: 토큰화에 사용할 모델명
            provider_type: Provider 타입 (None이면 현재 Provider 사용)

        Returns:
            int: 토큰 수
        """
        factory = cls.get_factory(provider_type)
        return factory.count_tokens(text, model_name)

    @classmethod
    def get_current_provider(cls) -> Optional[ProviderType]:
        """현재 활성화된 Provider 타입을 반환한다."""
        return cls._current_provider

    @classmethod
    def is_initialized(cls, provider_type: ProviderType) -> bool:
        """특정 Provider가 초기화되었는지 확인한다."""
        return cls._initialized.get(provider_type, False)


# Vertex AI Provider 자동 등록
def _register_vertexai_provider() -> None:
    """Vertex AI Provider를 Registry에 등록한다."""
    try:
        from src.core.llm.providers.google.vertexai.factory import VertexAIProviderFactory

        ProviderRegistry.register(ProviderType.VERTEX_AI, VertexAIProviderFactory)
        logger.debug("Vertex AI provider registered")
    except ImportError as e:
        logger.warning(f"Failed to register Vertex AI provider: {e}")


# OpenAI Provider 자동 등록
def _register_openai_provider() -> None:
    """OpenAI Provider를 Registry에 등록한다."""
    try:
        from src.core.llm.providers.openai.factory import OpenAIProviderFactory

        ProviderRegistry.register(ProviderType.OPENAI, OpenAIProviderFactory)
        logger.debug("OpenAI provider registered")
    except ImportError as e:
        logger.debug(f"OpenAI provider not available: {e}")


# 모듈 로드 시 Provider 등록
_register_vertexai_provider()
_register_openai_provider()
