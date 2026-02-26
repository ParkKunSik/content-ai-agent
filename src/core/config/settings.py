"""
통합 설정 모듈

모든 설정 클래스를 합성하여 단일 Settings 인스턴스를 제공합니다.

사용법:
    from src.core.config.settings import settings

    # 새로운 접근 방식
    settings.server.HOST
    settings.vertex_ai.MODEL_ADVANCED
    settings.elasticsearch.REFERENCE.HOST
"""

import logging
import os
from enum import Enum
from typing import Any, Dict

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.llm.enums import ProviderType
from src.core.config.base import (
    ServerSettings,
    ProfileSettings,
    GCPSettings,
    AWSSettings,
    InternalSettings,
)
from src.core.config.analysis import AnalysisSettings
from src.core.config.llm import LLMGenerationSettings
from src.core.config.elasticsearch import ElasticsearchSettings
from src.core.config.providers.vertex_ai import VertexAISettings
from src.core.config.providers.openai import OpenAISettings
from src.core.config.providers.gemini_api import GeminiAPISettings

logger = logging.getLogger("config")


class DeployTarget(str, Enum):
    """배포 대상 환경"""
    LOCAL = "LOCAL"   # 로컬 개발 (.env 파일만 사용)
    GCP = "GCP"       # GCP 환경 (Secret Manager에서 overwrite)
    AWS = "AWS"       # AWS 환경 (Secrets Manager에서 overwrite)


def _find_project_root():
    """프로젝트 루트 경로 탐색"""
    current = os.getcwd()
    root_candidates = [
        current,
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ]

    for root in root_candidates:
        if os.path.exists(os.path.join(root, ".env.local")):
            return root

    return None


def _find_env_files():
    """
    환경변수 파일 목록 반환 (존재하는 파일만)

    우선순위: .env.local < .env.vertex_ai < .env.openai < .env.gemini_api
    뒤에 있는 파일이 앞 파일을 덮어씁니다.
    """
    root = _find_project_root()
    if not root:
        return None

    env_files = [
        '.env.local',       # 공통 설정
        '.env.vertex_ai',   # Vertex AI 전용
        '.env.openai',      # OpenAI 전용
        '.env.gemini_api',  # Gemini API 전용
    ]

    existing_files = []
    for env_file in env_files:
        path = os.path.join(root, env_file)
        if os.path.exists(path):
            existing_files.append(path)

    return tuple(existing_files) if existing_files else None


def _deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    딕셔너리를 깊이 병합합니다.

    중첩된 딕셔너리는 재귀적으로 병합되며, updates의 값이 base를 덮어씁니다.

    Args:
        base: 기본 딕셔너리 (in-place 수정됨)
        updates: 업데이트할 값들

    Returns:
        병합된 딕셔너리 (base와 동일 객체)
    """
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _fetch_secrets_from_provider(
    deploy_target: DeployTarget,
    env: str,
    gcp_settings: "GCPSettings",
    aws_settings: "AWSSettings"
) -> Dict[str, Any]:
    """
    Secret Manager에서 설정을 가져온다.

    Args:
        deploy_target: 배포 대상 (GCP, AWS)
        env: 환경 (dev, prod)
        gcp_settings: GCP 설정 (project_id, secret_id 등)
        aws_settings: AWS 설정 (region, secret_name 등)

    Returns:
        설정 딕셔너리
    """
    if deploy_target == DeployTarget.GCP:
        from src.core.config.secrets.gcp import GCPSecretProvider
        # Secret ID: 명시적 지정 또는 기본 패턴 사용
        secret_id = gcp_settings.SECRET_ID or f"{env}-content-ai-config"
        provider = GCPSecretProvider(gcp_settings.PROJECT_ID)
        return provider.fetch_secrets(secret_id)

    elif deploy_target == DeployTarget.AWS:
        from src.core.config.secrets.aws import AWSSecretProvider
        # Secret 식별: ARN > Name > 기본 패턴
        secret_id = (
            aws_settings.SECRET_ARN
            or aws_settings.SECRET_NAME
            or f"{env}/content-ai/config"
        )
        provider = AWSSecretProvider(region=aws_settings.REGION)
        return provider.fetch_secrets(secret_id)

    return {}


ENV_FILES = _find_env_files()
PROJECT_ROOT = _find_project_root()

# 환경변수 로드 (다중 파일)
if ENV_FILES:
    for env_file in ENV_FILES:
        load_dotenv(env_file, override=True)
    logger.info(f"Loaded env files: {[os.path.basename(f) for f in ENV_FILES]}")


class Settings(BaseSettings):
    """
    통합 설정 클래스

    설정 Overwrite 단계:
    1. 기본값으로 Settings 인스턴스 생성
    2. 로컬 .env 파일이 존재하면 해당 내용으로 업데이트
    3. 배포 환경이 LOCAL이 아니면 Secret Manager에서 추가 업데이트 (deep merge)

    환경변수는 '__' 구분자로 중첩 접근합니다.
    예: VERTEX_AI__MODEL_ADVANCED=gemini-2.5-pro
    """

    # 배포 대상
    deploy_target: DeployTarget = DeployTarget.LOCAL

    # 공통 설정
    server: ServerSettings = ServerSettings()
    profile: ProfileSettings = ProfileSettings()
    gcp: GCPSettings = GCPSettings()
    aws: AWSSettings = AWSSettings()
    internal: InternalSettings = InternalSettings()

    # Provider 선택
    llm_provider: ProviderType = ProviderType.VERTEX_AI

    # Provider별 설정
    vertex_ai: VertexAISettings = VertexAISettings()
    openai: OpenAISettings = OpenAISettings()
    gemini_api: GeminiAPISettings = GeminiAPISettings()

    # ES 설정
    elasticsearch: ElasticsearchSettings = ElasticsearchSettings()

    # 분석 설정
    analysis: AnalysisSettings = AnalysisSettings()

    # LLM 생성 설정
    llm: LLMGenerationSettings = LLMGenerationSettings()

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )


def _init_settings() -> Settings:
    """
    설정 초기화

    Overwrite 단계:
    1. 기본값으로 Settings 인스턴스 생성
    2. 로컬 .env 파일이 존재하면 해당 내용으로 업데이트 (pydantic-settings 자동 처리)
    3. 배포 환경이 LOCAL이 아니면 Secret Manager에서 추가 업데이트
    """
    # -------------------------------------------------------------------------
    # Step 1 & 2: 기본값 + 로컬 .env 파일 로드
    # pydantic-settings가 자동으로 처리:
    # - 클래스에 정의된 기본값
    # - ENV_FILES에 지정된 .env 파일들 (존재하는 경우)
    # - 환경변수
    # -------------------------------------------------------------------------
    config = Settings()
    logger.debug(f"Step 1&2: Loaded defaults + env files: {ENV_FILES}")

    # -------------------------------------------------------------------------
    # Step 3: Secret Manager에서 추가 업데이트 (배포 환경이 LOCAL이 아닐 때)
    # -------------------------------------------------------------------------
    if config.deploy_target != DeployTarget.LOCAL:
        logger.info(f"Step 3: DEPLOY_TARGET={config.deploy_target}, fetching secrets...")

        try:
            secrets = _fetch_secrets_from_provider(
                deploy_target=config.deploy_target,
                env=config.profile.ENV,
                gcp_settings=config.gcp,
                aws_settings=config.aws
            )

            if secrets:
                # 현재 설정을 딕셔너리로 변환
                current_config = config.model_dump()
                # Secret Manager 값으로 deep update (부분 덮어쓰기)
                _deep_update(current_config, secrets)
                # 병합된 값으로 Settings 재생성
                config = Settings(**current_config)
                logger.info(f"Step 3: Settings updated from {config.deploy_target} Secret Manager")

        except Exception as e:
            logger.error(f"Failed to fetch secrets: {e}")
            raise RuntimeError(
                f"Could not load config from {config.deploy_target} Secret Manager. "
                f"ENV={config.profile.ENV}"
            ) from e

    # -------------------------------------------------------------------------
    # 후처리: GCP 인증 경로 절대경로 변환
    # -------------------------------------------------------------------------
    if config.gcp.CREDENTIALS_PATH and not os.path.isabs(config.gcp.CREDENTIALS_PATH):
        if PROJECT_ROOT:
            config.gcp.CREDENTIALS_PATH = os.path.abspath(
                os.path.join(PROJECT_ROOT, config.gcp.CREDENTIALS_PATH)
            )

    logger.info(
        f"Config loaded - "
        f"DEPLOY_TARGET: {config.deploy_target}, "
        f"Provider: {config.llm_provider}, "
        f"ENV: {config.profile.ENV}"
    )
    return config


# 전역 설정 인스턴스
settings = _init_settings()

__all__ = ["settings", "Settings", "DeployTarget"]
