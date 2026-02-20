import json
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.llm.enums import ProviderType

# GCP SDK는 필요할 때만 import (Lambda viewer 모드에서는 불필요)
try:
    from google.cloud import secretmanager
    HAS_GCP_SECRET_MANAGER = True
except ImportError:
    secretmanager = None
    HAS_GCP_SECRET_MANAGER = False

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
    # [Server Configuration]
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # [Profile Configuration]
    ENV: str = "local"

    # [GCP Configuration]
    GCP_PROJECT_ID: str = "local-development"
    GCP_REGION: str = "asia-northeast3"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # [Internal Identity]
    INTERNAL_AGENT_ID: str = "local-content-ai-agent-v1"

    # [LLM Provider Configuration]
    LLM_PROVIDER: ProviderType = ProviderType.VERTEX_AI

    # [Google Vertex AI Model Configuration]
    VERTEX_AI_MODEL_PRO: str = "gemini-2.5-pro"
    VERTEX_AI_MODEL_FLASH: str = "gemini-2.5-flash"

    # [OpenAI Configuration]
    OPENAI_API_KEY: Optional[str] = None
    # OPENAI_ORG_ID: OpenAI 조직 식별자 (Optional)
    # - 용도: API 호출 시 특정 조직의 크레딧/사용량으로 청구할지 지정
    # - 확인 방법: https://platform.openai.com/settings/organization/general
    #   Settings(⚙️) → Organization → General → Organization ID
    # - 형식: "org-xxxxxxxxxxxxxxxxxxxx" (예: org-lyRKfZrmpm4aogwP8hMYtqtb)
    # - 필요 여부:
    #   * 개인 계정/단일 조직: 생략 가능 (API 키에 연결된 기본 조직 사용)
    #   * 여러 조직에 소속된 경우: 필요 (특정 조직 지정)
    #   * 팀/기업 계정: 권장 (청구 명확화)
    OPENAI_ORG_ID: Optional[str] = None
    OPENAI_MODEL_PRO: str = "gpt-4o"
    OPENAI_MODEL_FLASH: str = "gpt-4o-mini"

    # [Analysis Configuration]
    MAX_MAIN_SUMMARY_CHARS: int = 300
    MAX_CATEGORY_SUMMARY_CHARS: int = 50
    MAX_INSIGHT_ITEM_CHARS_ANALYSIS: int = 50  # good_points, caution_points 분석용 최대 길이
    MAX_INSIGHT_ITEM_CHARS_REFINE: int = 30  # good_points, caution_points 정제용 최대 길이

    # [Validation Configuration]
    # 스키마 검증 엄격도 제어 (True: 에러 발생, False: 경고만)
    STRICT_VALIDATION: bool = False

    # [Elasticsearch Configuration]
    # 참조용 ES 클러스터 (기존 wadiz 데이터 조회)
    ES_REFERENCE_HOST: str = "localhost"
    ES_REFERENCE_PORT: Optional[int] = 9200
    ES_REFERENCE_USERNAME: Optional[str] = None
    ES_REFERENCE_PASSWORD: Optional[str] = None
    ES_REFERENCE_USE_SSL: bool = False
    ES_REFERENCE_VERIFY_CERTS: bool = False
    ES_REFERENCE_TIMEOUT: int = 30

    # 메인 ES 클러스터 (분석 결과 저장)
    ES_MAIN_HOST: str = "localhost"
    ES_MAIN_PORT: Optional[int] = 9201
    ES_MAIN_USERNAME: Optional[str] = None
    ES_MAIN_PASSWORD: Optional[str] = None
    ES_MAIN_USE_SSL: bool = False
    ES_MAIN_VERIFY_CERTS: bool = False
    ES_MAIN_TIMEOUT: int = 30
    
    # ES 인덱스/Alias 설정 (기존 - 하위 호환)
    ANALYSIS_RESULT_INDEX: str = "core-content-analysis-result"  # 인덱스 생성용
    ANALYSIS_RESULT_ALIAS: str = "core-content-analysis-result-alias"  # 조회/저장용

    # ES 인덱스/Alias 설정 (Provider별)
    ANALYSIS_RESULT_VERTEX_AI_INDEX: str = "core-content-analysis-result-vertex-ai"
    ANALYSIS_RESULT_VERTEX_AI_ALIAS: str = "core-content-analysis-result-vertex-ai-alias"
    ANALYSIS_RESULT_OPENAI_INDEX: str = "core-content-analysis-result-openai"
    ANALYSIS_RESULT_OPENAI_ALIAS: str = "core-content-analysis-result-openai-alias"

    # Provider 무관하게 기본 인덱스/Alias 사용 여부
    # True: Provider 타입과 상관없이 ANALYSIS_RESULT_INDEX/ALIAS 사용 (기본값)
    # False: Provider별 인덱스/Alias 사용
    USE_DEFAULT_ES_INDEX: bool = True

    @field_validator('ES_REFERENCE_PORT', 'ES_MAIN_PORT', mode='before')
    @classmethod
    def validate_port(cls, v):
        """빈 문자열을 None으로 변환"""
        if v == '' or v is None:
            return None
        return int(v)

    # [LLM Generation Configuration]
    # ============================================================================
    # [Vertex AI / Gemini 모델 토큰 제한 가이드]
    # ============================================================================
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
    #
    # ============================================================================
    # [OpenAI 모델 가이드] (2026-02 기준)
    # ============================================================================
    #
    # [모델 계열 분류]
    # - GPT-4o 시리즈: 레거시 멀티모달 모델 (temperature 지원)
    # - GPT-4.1 시리즈: 코딩/지시 따르기 향상 (temperature 지원)
    # - GPT-5 시리즈: Reasoning 내장 플래그십 (temperature 미지원)
    # - O-시리즈: Reasoning 전용 모델 (temperature 미지원)
    #
    # ----------------------------------------------------------------------------
    # [GPT-4o 시리즈] - 레거시, temperature 지원 (0-2)
    # ----------------------------------------------------------------------------
    # - gpt-4o:
    #   * Context: 128K, Output: 16K
    #   * 가격: $2.50/$10.00 per 1M tokens (input/output)
    #   * 특징: 멀티모달(텍스트, 이미지, 오디오), 빠른 속도
    #
    # - gpt-4o-mini:
    #   * Context: 128K, Output: 16K
    #   * 가격: $0.15/$0.60 per 1M tokens
    #   * 특징: GPT-4o 대비 60% 이상 저렴
    #
    # ----------------------------------------------------------------------------
    # [GPT-4.1 시리즈] - 2025년 4월 출시, temperature 지원
    # ----------------------------------------------------------------------------
    # - gpt-4.1:
    #   * Context: 1M, Output: 32K
    #   * 가격: $2.00/$8.00 per 1M tokens
    #   * 특징: GPT-4o 대비 코딩/지시 따르기 대폭 향상
    #
    # - gpt-4.1-mini / gpt-4.1-nano:
    #   * Context: 1M
    #   * 특징: 저비용/초저비용 버전
    #
    # ----------------------------------------------------------------------------
    # [GPT-5 시리즈] - 2025년 8월 출시, temperature 미지원 (1 고정)
    # ----------------------------------------------------------------------------
    # - gpt-5:
    #   * Context: 400K
    #   * 가격: $1.25/$10.00 per 1M tokens
    #   * 특징: Reasoning 내장 플래그십 모델
    #
    # - gpt-5-mini / gpt-5-nano:
    #   * 특징: 저비용/초저비용 버전
    #
    # - [주의] 샘플링 파라미터 미지원:
    #   * temperature, top_p, presence_penalty, frequency_penalty 사용 불가
    #   * 대체 파라미터: reasoning_effort, verbosity
    #
    # ----------------------------------------------------------------------------
    # [O-시리즈 (Reasoning 전용)] - temperature 미지원 (1 고정)
    # ----------------------------------------------------------------------------
    # - o1, o1-mini, o1-preview: 초기 Reasoning 모델
    # - o3, o3-mini, o3-pro: 고급 Reasoning 모델
    # - o4-mini: 빠른 Reasoning 모델 (수학, 코딩, 시각적 작업 최적화)
    #
    # - [주의] 샘플링 파라미터 미지원:
    #   * temperature, top_p, presence_penalty, frequency_penalty 사용 불가
    #   * 내부 reasoning tokens가 output으로 과금됨
    #   * 단순 작업에는 GPT-4o/4.1 사용 권장 (비용 효율)
    #
    # ============================================================================
    # - 현재 설정값: 65,000 (Vertex AI 최대치 기준, OpenAI 사용 시 모델별 제한 자동 적용)
    MAX_OUTPUT_TOKENS: int = 65000
    
    model_config = SettingsConfigDict(
        env_file=ENV_LOCAL_PATH, 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

def fetch_config_from_gsm(env: str, project_id: str) -> Dict[str, Any]:
    """Fetches configuration JSON from Google Secret Manager."""
    if not HAS_GCP_SECRET_MANAGER:
        raise RuntimeError(
            "google-cloud-secret-manager is not installed. "
            "Install with: pip install google-cloud-secret-manager"
        )

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

    # Convert relative path to absolute path for credentials if needed
    if config.GOOGLE_APPLICATION_CREDENTIALS and not os.path.isabs(config.GOOGLE_APPLICATION_CREDENTIALS):
        if ENV_LOCAL_PATH:
            root_dir = os.path.dirname(ENV_LOCAL_PATH)
            config.GOOGLE_APPLICATION_CREDENTIALS = os.path.abspath(
                os.path.join(root_dir, config.GOOGLE_APPLICATION_CREDENTIALS)
            )
            logger.info(f"Resolved credentials path to: {config.GOOGLE_APPLICATION_CREDENTIALS}")

    logger.info(f"Loaded Config - Project: {config.GCP_PROJECT_ID}, Region: {config.GCP_REGION}")
    return config

# Global settings instance
settings = init_settings()