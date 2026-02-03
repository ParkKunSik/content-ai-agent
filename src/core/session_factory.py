import logging
from typing import Optional, Dict, Any

import google.genai as genai
from google.genai import types

from src.core.config import settings
from src.core.async_genai_session import AsyncGenAISession
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.mime_type import MimeType
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class SessionFactory:
    """
    Registry-based Factory for google-genai Chat sessions.
    ModelFactory 구조를 기반으로 한 페르소나별 GenerateContentConfig 관리.
    """
    _client: Optional['genai.Client'] = None
    _configs: Dict[PersonaType, Optional['types.GenerateContentConfig']] = {}

    @classmethod
    def initialize(cls):
        """
        google-genai 클라이언트 초기화 및 모든 페르소나별 Config 등록.
        ModelFactory.initialize()와 동일한 패턴으로 구현.
        """
        logger.info(f"Initializing SessionFactory with google-genai SDK in region: {settings.GCP_REGION}...")
        
        # Resolve credentials with proper scope for google-genai
        credentials = None
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            from google.oauth2 import service_account
            try:
                base_credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_APPLICATION_CREDENTIALS
                )
                # Add required scope for Vertex AI
                credentials = base_credentials.with_scopes([
                    'https://www.googleapis.com/auth/cloud-platform'
                ])
                logger.info(f"Loaded credentials from: {settings.GOOGLE_APPLICATION_CREDENTIALS}")
            except Exception as e:
                logger.warning(f"Failed to load credentials file, falling back to default: {e}")

        # Initialize google-genai client
        cls._client = genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION,
            credentials=credentials
        )
        
        cls._configs.clear()
        
        # Use the singleton PromptManager to get the renderer
        prompt_renderer = PromptManager().renderer

        try:
            for persona_type in PersonaType:
                # 1. Resolve Model Name
                model_name = persona_type.model_name_getter(settings)

                # 2. Resolve System Instruction
                system_instruction = persona_type.get_instruction(prompt_renderer)
                
                # 3. Register Config
                cls._register_config(persona_type, system_instruction)

            logger.info(f"SessionFactory initialized with {len(cls._configs)} configs.")

        except Exception as e:
            logger.error(f"Failed to initialize SessionFactory: {e}")
            raise RuntimeError("SessionFactory initialization failed") from e

    @classmethod
    def _register_config(cls, persona_type: PersonaType, system_instruction: Optional[str]):
        """Helper to create and register a GenerateContentConfig instance."""
        logger.debug(f"Registering config: {persona_type.value}")
        try:
            config = types.GenerateContentConfig(
                temperature=persona_type.temperature,
                system_instruction=system_instruction
            )
            cls._configs[persona_type] = config
        except Exception as e:
            logger.error(f"Error creating config for {persona_type.value}: {e}")
            raise

    @classmethod
    def start_session(
        cls, 
        persona_type: PersonaType, 
        mime_type: MimeType = MimeType.TEXT_PLAIN,
        schema: Optional[Dict[str, Any]] = None
    ) -> AsyncGenAISession:
        """
        새로운 비동기 세션 래퍼를 시작한다.
        ModelFactory.get_model()과 유사한 패턴으로 구현.
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
            response_schema=schema
        )
            
        # 모델명 해결 (PersonaType에서 가져옴)
        model_name = persona_type.model_name_getter(settings)
        
        # AsyncGenAISession 래퍼 반환
        return AsyncGenAISession(
            client=cls._client,
            model_name=model_name,
            config=session_config
        )
    
    @classmethod
    def count_tokens(cls, text: str, persona_type: PersonaType) -> int:
        """
        텍스트의 토큰 수를 카운트한다.
        ModelFactory.get_model() 패턴을 대체.
        """
        if cls._client is None:
            cls.initialize()
        
        # 모델명 해결
        model_name = persona_type.model_name_getter(settings)
        
        try:
            # google-genai SDK의 count_tokens 사용
            result = cls._client.models.count_tokens(
                model=model_name,
                contents=text
            )
            return result.total_tokens
        except Exception as e:
            logger.warning(f"Failed to count tokens with google-genai SDK: {e}")
            # 폴백: 대략적인 토큰 추정
            return len(text) // 2