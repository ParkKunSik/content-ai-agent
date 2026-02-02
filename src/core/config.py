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

    # [Model Configuration]
    VERTEX_AI_MODEL_PRO: str = "gemini-2.5-pro"
    VERTEX_AI_MODEL_FLASH: str = "gemini-2.5-flash"

    # [Analysis Configuration]
    MAX_MAIN_SUMMARY_CHARS: int = 300
    MAX_CATEGORY_SUMMARY_CHARS: int = 50
    
    # [Validation Configuration]
    # 스키마 검증 엄격도 제어 (True: 에러 발생, False: 경고만)
    STRICT_VALIDATION: bool = False

    # [LLM Generation Configuration]
    # 입력/출력 토큰 제한 가이드 (Vertex AI 기준):
    # - Gemini 2.5 Pro/Flash:
    #   * 입력 토큰 제한: 약 1M (1,048,576) 토큰 지원
    #   * 출력 토큰 제한: 최대 65,535 토큰
    # - Gemini 3.0 Pro/Flash Preview:
    #   * 입력 토큰 제한: 약 1M (1,048,576) 토큰 지원
    #   * 출력 토큰 제한 (Output Token Limit): 공식 사양은 65,536을 명시하나, 
    #     Vertex AI Preview 환경 실제 호출 시 32,768 토큰까지만 안정적으로 반환되는 제약이 확인됨.
    #   * [중요] Preview 안정성 특성: 
    #     - 32,768 미만에서도 불안정한 경우가 있으며, GA(General Availability) 전 자원 보호를 위한 엄격한 가드레일이 존재함.
    #     - 특히 입력 토큰이 매우 큰 경우, 전체 리소스 사용량에 비례하여 출력 토큰 한도가 유동적으로 줄어들 수 있음.
    #     - 출력이 짧더라도 finish_reason='MAX_TOKENS'가 반환되는 현상이 발생할 수 있음.
    # - 현재 설정값: 65,000 (설정은 최대치로 하되, Preview 모델 사용 시 안정성을 위해 입력을 적절히 청킹하는 전략 권장)
    MAX_OUTPUT_TOKENS: int = 65000
    
    model_config = SettingsConfigDict(
        env_file=ENV_LOCAL_PATH, 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

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