import logging
from typing import Optional, Dict
import vertexai
from vertexai.generative_models import GenerativeModel

from src.core.config import settings
from src.schemas.enums.persona_type import PersonaType
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class ModelFactory:
    """
    Registry-based Factory for Vertex AI GenerativeModel instances.
    Ensures correct region initialization and eager loading of models.
    """
    _models: Dict[PersonaType, GenerativeModel] = {}

    @classmethod
    def initialize(cls):
        """
        Initializes and registers all required model instances at application startup.
        Ensures vertexai is initialized with the correct project, region, and credentials.
        """
        logger.info(f"Initializing ModelFactory in region: {settings.GCP_REGION}...")
        
        # Resolve credentials to avoid async REST warning
        credentials = None
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            from google.oauth2 import service_account
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_APPLICATION_CREDENTIALS
                )
                logger.info(f"Loaded credentials from: {settings.GOOGLE_APPLICATION_CREDENTIALS}")
            except Exception as e:
                logger.warning(f"Failed to load credentials file, falling back to default: {e}")

        # Explicitly initialize vertexai and aiplatform
        vertexai.init(
            project=settings.GCP_PROJECT_ID, 
            location=settings.GCP_REGION,
            credentials=credentials
        )
        # Also initialize the underlying aiplatform to ensure async clients get credentials
        from google.cloud import aiplatform
        from google.cloud.aiplatform import initializer
        
        aiplatform.init(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION,
            credentials=credentials
        )
        
        # Satisfy the SDK's internal check for async REST credentials to suppress the warning
        if credentials and hasattr(initializer, "_set_async_rest_credentials"):
            try:
                initializer._set_async_rest_credentials(credentials)
            except Exception:
                pass
        
        cls._models.clear()
        
        # Use the singleton PromptManager to get the renderer
        prompt_renderer = PromptManager().renderer

        try:
            for model_type in PersonaType:
                # 1. Resolve Model Name
                model_name = model_type.model_name_getter(settings)

                # 2. Resolve System Instruction
                system_instruction = model_type.get_instruction(prompt_renderer)
                
                # 3. Register Model
                cls._register(model_type, model_name, system_instruction)

            logger.info(f"ModelFactory initialized with {len(cls._models)} models.")

        except Exception as e:
            logger.error(f"Failed to initialize ModelFactory: {e}")
            raise RuntimeError("ModelFactory initialization failed") from e

    @classmethod
    def _register(cls, model_type: PersonaType, model_name: str, system_instruction: Optional[str]):
        """Helper to create and register a model instance."""
        logger.debug(f"Registering model: {model_type.value} ({model_name})")
        try:
            # GenerativeModel uses the global vertexai.init values by default
            instance = GenerativeModel(
                model_name=model_name,
                system_instruction=[system_instruction] if system_instruction else None
            )
            cls._models[model_type] = instance
        except Exception as e:
            logger.error(f"Error creating model {model_type.value}: {e}")
            raise

    @classmethod
    def get_model(cls, model_type: PersonaType) -> GenerativeModel:
        """
        Retrieves a pre-registered model instance.
        """
        instance = cls._models.get(model_type)
        if not instance:
            raise ValueError(f"ModelType '{model_type.value}' is not registered. Call initialize() first.")
        return instance