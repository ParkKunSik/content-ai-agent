"""OpenAI Provider Factory 구현"""

import logging
from typing import Any, Dict, Optional

from src.core.llm.base.factory import LLMProviderFactory
from src.core.llm.enums import ResponseFormat
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
        response_schema: Optional[dict] = None,
    ) -> OpenAISession:
        """
        새로운 OpenAI 세션을 시작한다.

        Args:
            persona_config: 페르소나 설정 (모델명, 온도 등)
            response_schema: JSON 응답 시 스키마 (optional)

        Returns:
            OpenAISession: 세션 인스턴스
        """
        if cls._client is None:
            cls.initialize()

        # response_format 결정
        response_format = None
        if persona_config.response_format == ResponseFormat.JSON:
            if response_schema or persona_config.response_schema:
                # Structured Outputs 사용 (GPT-4 이상에서 지원)
                schema = response_schema or persona_config.response_schema
                response_format = cls._build_json_schema_format(schema)
            else:
                # 기본 JSON 모드
                response_format = {"type": "json_object"}

        return OpenAISession(
            client=cls._client,
            model_name=persona_config.model_name,
            temperature=persona_config.temperature,
            system_instruction=persona_config.system_instruction,
            response_format=response_format,
        )

    @classmethod
    def _build_json_schema_format(cls, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        JSON Schema를 OpenAI Structured Outputs 형식으로 변환한다.

        OpenAI Structured Outputs 요구사항:
        - 모든 object 타입에 'additionalProperties': false 필수
        - $defs → definitions 변환 필요
        - $ref 경로도 함께 변환

        Args:
            schema: JSON Schema 딕셔너리

        Returns:
            OpenAI response_format 딕셔너리
        """
        import copy

        # 스키마 복사 후 변환
        converted_schema = cls._convert_schema_for_openai(copy.deepcopy(schema))

        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.get("title", "response_schema"),
                "strict": True,
                "schema": converted_schema,
            },
        }

    @classmethod
    def _convert_schema_for_openai(cls, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pydantic JSON Schema를 OpenAI Structured Outputs 호환 형식으로 변환한다.

        변환 내용:
        1. 모든 object에 'additionalProperties': false 추가
        2. '$defs' → 'definitions' 키 변환
        3. '$ref' 경로 변환 (#/$defs/ → #/definitions/)

        Args:
            schema: 원본 JSON Schema

        Returns:
            OpenAI 호환 JSON Schema
        """
        # $defs → definitions 변환
        if "$defs" in schema:
            schema["definitions"] = schema.pop("$defs")
            # definitions 내부 항목들도 재귀 처리
            for key, value in schema["definitions"].items():
                if isinstance(value, dict):
                    schema["definitions"][key] = cls._convert_schema_for_openai(value)

        # $ref 경로 변환 - OpenAI는 $ref와 다른 키워드 함께 사용 불가
        if "$ref" in schema:
            schema["$ref"] = schema["$ref"].replace("#/$defs/", "#/definitions/")
            # $ref가 있으면 다른 키워드 제거 (OpenAI 제약)
            keys_to_remove = [k for k in schema.keys() if k not in ("$ref",)]
            for key in keys_to_remove:
                del schema[key]
            return schema  # $ref만 있는 경우 더 이상 처리 불필요

        # object 타입에 additionalProperties: false 및 required 처리
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            # OpenAI는 모든 properties가 required에 포함되어야 함
            if "properties" in schema:
                schema["required"] = list(schema["properties"].keys())

        # properties 내부 재귀 처리
        if "properties" in schema:
            for key, value in schema["properties"].items():
                if isinstance(value, dict):
                    schema["properties"][key] = cls._convert_schema_for_openai(value)

        # items (array) 재귀 처리
        if "items" in schema and isinstance(schema["items"], dict):
            schema["items"] = cls._convert_schema_for_openai(schema["items"])

        # allOf, anyOf, oneOf 재귀 처리
        for combinator in ["allOf", "anyOf", "oneOf"]:
            if combinator in schema:
                schema[combinator] = [
                    cls._convert_schema_for_openai(item) if isinstance(item, dict) else item
                    for item in schema[combinator]
                ]

        return schema

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
