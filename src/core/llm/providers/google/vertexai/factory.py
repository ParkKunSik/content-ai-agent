"""Vertex AI Provider Factory 구현"""

import logging
from typing import Any, Dict, Optional

import google.genai as genai
from google.genai import types

from src.core.config import settings
from src.core.llm.base.factory import LLMProviderFactory
from src.core.llm.enums import ResponseFormat
from src.core.llm.models import PersonaConfig
from src.core.llm.providers.google.vertexai.session import VertexAISession
from src.schemas.enums.mime_type import MimeType
from src.schemas.enums.persona_type import PersonaType
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class VertexAIProviderFactory(LLMProviderFactory):
    """
    Vertex AI Provider Factory.
    LLMProviderFactory ABC를 구현하며,
    google-genai SDK (vertexai=True) 기반의 세션을 생성한다.
    """

    _client: Optional["genai.Client"] = None
    _configs: Dict[PersonaType, Optional["types.GenerateContentConfig"]] = {}

    @classmethod
    def initialize(cls) -> None:
        """
        google-genai 클라이언트 초기화 및 모든 페르소나별 Config 등록.
        """
        logger.info(f"Initializing VertexAIProviderFactory in region: {settings.GCP_REGION}...")

        # Resolve credentials with proper scope for google-genai
        credentials = None
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            import os

            if not os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                logger.error(f"Credentials file NOT FOUND at: {settings.GOOGLE_APPLICATION_CREDENTIALS}")
            else:
                from google.oauth2 import service_account

                try:
                    base_credentials = service_account.Credentials.from_service_account_file(
                        settings.GOOGLE_APPLICATION_CREDENTIALS
                    )
                    # Add required scope for Vertex AI
                    credentials = base_credentials.with_scopes(["https://www.googleapis.com/auth/cloud-platform"])
                    logger.info(f"Successfully loaded credentials from: {settings.GOOGLE_APPLICATION_CREDENTIALS}")
                except Exception as e:
                    logger.warning(f"Failed to load credentials file: {e}")

        # Initialize google-genai client with Vertex AI mode
        cls._client = genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION,
            credentials=credentials,
        )

        cls._configs.clear()

        # Use the singleton PromptManager to get the renderer
        prompt_renderer = PromptManager().renderer

        try:
            for persona_type in PersonaType:
                # 1. Resolve System Instruction
                system_instruction = persona_type.get_instruction(prompt_renderer)

                # 2. Register Config
                cls._register_config(persona_type, system_instruction)

            logger.info(f"VertexAIProviderFactory initialized with {len(cls._configs)} configs.")

        except Exception as e:
            logger.error(f"Failed to initialize VertexAIProviderFactory: {e}")
            raise RuntimeError("VertexAIProviderFactory initialization failed") from e

    @classmethod
    def _register_config(cls, persona_type: PersonaType, system_instruction: Optional[str]) -> None:
        """Helper to create and register a GenerateContentConfig instance."""
        logger.debug(f"Registering config: {persona_type.value}")
        try:
            config = types.GenerateContentConfig(
                temperature=persona_type.temperature,
                system_instruction=system_instruction,
            )
            cls._configs[persona_type] = config
        except Exception as e:
            logger.error(f"Error creating config for {persona_type.value}: {e}")
            raise

    @classmethod
    def start_session(
        cls,
        persona_config: PersonaConfig,
    ) -> VertexAISession:
        """
        새로운 Vertex AI 세션을 시작한다.

        Args:
            persona_config: 페르소나 설정 (모델명, 온도, response_schema 등)

        Returns:
            VertexAISession: 세션 인스턴스
        """
        if cls._client is None:
            cls.initialize()

        # response_format에 따른 mime_type 결정
        mime_type = "application/json" if persona_config.response_format == ResponseFormat.JSON else "text/plain"

        # Pydantic 모델 → JSON Schema dict 변환
        schema_dict = None
        if persona_config.response_schema:
            schema_dict = persona_config.response_schema.model_json_schema()

        # 세션 설정 생성
        session_config = types.GenerateContentConfig(
            temperature=persona_config.temperature,
            system_instruction=persona_config.system_instruction,
            response_mime_type=mime_type,
            response_schema=schema_dict,
        )

        return VertexAISession(
            client=cls._client,
            model_name=persona_config.model_name,
            config=session_config,
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
        if cls._client is None:
            cls.initialize()

        try:
            result = cls._client.models.count_tokens(model=model_name, contents=text)
            return result.total_tokens
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}")
            # 폴백: 대략적인 토큰 추정
            return len(text) // 2

    @classmethod
    def get_provider_name(cls) -> str:
        """Provider 이름을 반환한다."""
        return "VERTEX_AI"

    # ===== 하위 호환성을 위한 레거시 인터페이스 =====

    @classmethod
    def start_session_legacy(
        cls,
        persona_type: PersonaType,
        mime_type: MimeType = MimeType.TEXT_PLAIN,
        schema: Optional[Dict[str, Any]] = None,
    ) -> VertexAISession:
        """
        [레거시] 기존 인터페이스 호환을 위한 세션 시작 메서드.
        새 코드에서는 start_session()을 사용하세요.
        """
        if cls._client is None:
            cls.initialize()

        base_config = cls._configs.get(persona_type)
        if not base_config:
            raise ValueError(f"PersonaType '{persona_type.value}' is not registered. Call initialize() first.")

        # 기본 설정을 복사하고 세션별 파라미터로 오버라이드
        session_config = types.GenerateContentConfig(
            temperature=base_config.temperature,
            system_instruction=base_config.system_instruction,
            response_mime_type=mime_type.value,
            response_schema=schema,
        )

        # 모델명 해결 (PersonaType에서 가져옴)
        model_name = persona_type.model_name_getter(settings)

        return VertexAISession(
            client=cls._client,
            model_name=model_name,
            config=session_config,
        )

    @classmethod
    def count_tokens_legacy(cls, text: str, persona_type: PersonaType) -> int:
        """
        [레거시] 기존 인터페이스 호환을 위한 토큰 카운트 메서드.
        새 코드에서는 count_tokens()를 사용하세요.
        """
        model_name = persona_type.model_name_getter(settings)
        return cls.count_tokens(text, model_name)


# 하위 호환성을 위한 별칭
GoogleProviderFactory = VertexAIProviderFactory


class SessionFactory(VertexAIProviderFactory):
    """
    [Deprecated] VertexAIProviderFactory의 별칭.
    기존 코드 호환성을 위해 유지됨.
    """

    @classmethod
    def start_session(
        cls,
        persona_type: PersonaType,
        mime_type: MimeType = MimeType.TEXT_PLAIN,
        schema: Optional[Dict[str, Any]] = None,
    ) -> VertexAISession:
        """기존 start_session 인터페이스 유지."""
        return cls.start_session_legacy(persona_type, mime_type, schema)

    @classmethod
    def count_tokens(cls, text: str, persona_type: PersonaType) -> int:
        """기존 count_tokens 인터페이스 유지."""
        return cls.count_tokens_legacy(text, persona_type)
