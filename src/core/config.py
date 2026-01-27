import os
import json
import logging
from typing import Optional, Any, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict
from google.cloud import secretmanager
from dotenv import load_dotenv

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("config")

def find_env_local():
    """
    Search for .env.local in current directory or parent directories.
    """
    current = os.getcwd()
    # Also check relative to this file
    possible_paths = [
        os.path.join(current, ".env.local"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env.local")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

ENV_LOCAL_PATH = find_env_local()

# --- MANUALLY OVERRIDE ENV VARS FROM .env.local ---
if ENV_LOCAL_PATH:
    logger.info(f"Initializing using explicitly found file: {ENV_LOCAL_PATH}")
    load_dotenv(ENV_LOCAL_PATH, override=True)
else:
    logger.warning(".env.local not found in standard locations.")

class Settings(BaseSettings):
    """
    Application settings and configuration.
    """
    # [Profile Configuration]
    ENV: str = "local"

    # [GCP Configuration]
    GCP_PROJECT_ID: str = "local-development"
    GCP_REGION: str = "asia-northeast3"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # [Internal Identity]
    INTERNAL_AGENT_ID: str = "local-content-ai-agent-v1"

    # [System Instruction]
    SYSTEM_INSTRUCTION_VERSION: str = "v1"

    # [Redis Configuration]
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None

    # [Elasticsearch Configuration]
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ELASTICSEARCH_API_KEY: Optional[str] = None
    ELASTICSEARCH_INDEX_HISTORY: str = "local-content-ai-history"

    # [Model Configuration]
    VERTEX_AI_MODEL_PRO: str = "gemini-2.5-pro"
    VERTEX_AI_MODEL_FLASH: str = "gemini-2.5-flash"

    # [Analysis Configuration]
    MAX_MAIN_SUMMARY_CHARS: int = 300
    MAX_CATEGORY_SUMMARY_CHARS: int = 50

    # [LLM Generation Configuration]
    MAX_OUTPUT_TOKENS: int = 32000
    TEMPERATURE: float = 0.3

    model_config = SettingsConfigDict(
        env_file=ENV_LOCAL_PATH, 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    @property
    def redis_url(self) -> str:
        """Constructs a Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

def fetch_config_from_gsm(env: str, project_id: str) -> Dict[str, Any]:
    """Fetches configuration JSON from Google Secret Manager."""
    secret_id = f"{env}-content-ai-config"
    logger.info(f"Loading configuration from Secret Manager: {secret_id}")
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return json.loads(response.payload.data.decode("UTF-8"))
    except Exception as e:
        logger.error(f"Failed to load secret '{secret_id}': {e}")
        raise RuntimeError(f"Could not load config for ENV='{env}' from GSM.") from e

def init_settings() -> Settings:
    """Initializes settings based on the execution environment."""
    config = Settings()
    
    if not ENV_LOCAL_PATH and config.ENV != "local":
        env_profile = os.getenv("ENV")
        project_id = os.getenv("GCP_PROJECT_ID")
        if env_profile and project_id:
            secrets = fetch_config_from_gsm(env_profile, project_id)
            return Settings(**secrets)

    logger.info(f"Loaded Config - Project: {config.GCP_PROJECT_ID}, Region: {config.GCP_REGION}")
    return config

# Global settings instance
settings = init_settings()