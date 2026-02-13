"""OpenAI Provider Factory 구현"""

import logging
from typing import Any, Optional

from src.core.llm.base.factory import LLMProviderFactory
from src.core.llm.models import PersonaConfig
from src.core.llm.providers.openai.session import OpenAISession

logger = logging.getLogger(__name__)


class OpenAIProviderFactory(LLMProviderFactory):
    """
    OpenAI Provider Factory.
    LLMProviderFactory ABC를 구현하며,
    OpenAI API 기반의 세션을 생성한다.
    """

    _client: Optional[Any] = None  # openai.OpenAI
    _api_key: Optional[str] = None
    _org_id: Optional[str] = None

    @classmethod
    def initialize(cls) -> None:
        """
        OpenAI 클라이언트 초기화.
        """
        from src.core.config import settings

        logger.info("Initializing OpenAIProviderFactory...")

        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "openai package is not installed. "
                "Install it with: pip install openai"
            ) from e

        # 설정에서 API 키 가져오기
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in settings")

        org_id = getattr(settings, "OPENAI_ORG_ID", None)

        # OpenAI 클라이언트 초기화
        client_kwargs = {"api_key": api_key}
        if org_id:
            client_kwargs["organization"] = org_id

        cls._client = openai.OpenAI(**client_kwargs)
        cls._api_key = api_key
        cls._org_id = org_id

        logger.info("OpenAIProviderFactory initialized successfully.")

    @classmethod
    def start_session(
        cls,
        persona_config: PersonaConfig,
    ) -> OpenAISession:
        """
        새로운 OpenAI 세션을 시작한다.

        Args:
            persona_config: 페르소나 설정 (모델명, 온도, response_schema 등)

        Returns:
            OpenAISession: 세션 인스턴스
        """
        if cls._client is None:
            cls.initialize()

        return OpenAISession(
            client=cls._client,
            model_name=persona_config.model_name,
            temperature=persona_config.temperature,
            system_instruction=persona_config.system_instruction,
            response_schema=persona_config.response_schema,  # Pydantic 클래스 그대로
        )

    @classmethod
    def count_tokens(cls, text: str, model_name: str) -> int:
        """
        텍스트의 토큰 수를 계산한다.

        Args:
            text: 토큰 수를 계산할 텍스트
            model_name: 토큰화에 사용할 모델명

        Returns:
            int: 토큰 수
        """
        try:
            import tiktoken
        except ImportError:
            logger.warning("tiktoken not installed, using fallback estimation")
            return len(text) // 4

        try:
            encoding = tiktoken.encoding_for_model(model_name)
            return len(encoding.encode(text))
        except KeyError:
            # 모델에 맞는 인코딩이 없으면 기본 인코딩 사용
            try:
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
            except Exception as e:
                logger.warning(f"Failed to count tokens with tiktoken: {e}")
                return len(text) // 4

    @classmethod
    def get_provider_name(cls) -> str:
        """Provider 이름을 반환한다."""
        return "OPENAI"
