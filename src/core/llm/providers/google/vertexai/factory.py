"""Vertex AI Provider Factory 구현"""

import logging
from typing import Optional

import google.genai as genai
from google.genai import types

from src.core.config import settings
from src.core.llm.base.factory import LLMProviderFactory
from src.core.llm.enums import ResponseFormat
from src.core.llm.models import PersonaConfig
from src.core.llm.providers.google.vertexai.session import VertexAISession

logger = logging.getLogger(__name__)


class VertexAIProviderFactory(LLMProviderFactory):
    """
    Vertex AI Provider Factory.
    LLMProviderFactory ABC를 구현하며,
    google-genai SDK (vertexai=True) 기반의 세션을 생성한다.
    """

    _client: Optional["genai.Client"] = None

    @classmethod
    def initialize(cls) -> None:
        """
        google-genai 클라이언트 초기화.
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

        logger.info("VertexAIProviderFactory initialized.")

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
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
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
