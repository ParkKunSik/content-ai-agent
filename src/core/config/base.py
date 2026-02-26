"""공통 설정 클래스"""

from typing import Optional
from pydantic import BaseModel


class ServerSettings(BaseModel):
    """서버 설정"""
    HOST: str = "0.0.0.0"
    PORT: int = 8000


class ProfileSettings(BaseModel):
    """프로필 설정"""
    ENV: str = "local"  # local, dev, prod


class GCPSettings(BaseModel):
    """GCP 설정"""
    PROJECT_ID: str = "local-development"
    REGION: str = "asia-northeast3"
    CREDENTIALS_PATH: Optional[str] = None  # GOOGLE_APPLICATION_CREDENTIALS
    # Secret Manager 설정 (DEPLOY_TARGET=GCP 시 사용)
    # Secret ID 패턴: {ENV}-content-ai-config (기본값)
    # 명시적 지정 시 해당 값 사용
    SECRET_ID: Optional[str] = None


class AWSSettings(BaseModel):
    """AWS 설정 (DEPLOY_TARGET=AWS 시 사용)"""
    REGION: str = "ap-northeast-2"
    # Secret Manager 설정
    # Secret Name 패턴: {ENV}/content-ai/config (기본값)
    # 명시적 지정 시 해당 값 사용
    SECRET_NAME: Optional[str] = None
    SECRET_ARN: Optional[str] = None  # ARN 직접 지정 (우선순위 높음)
    # 인증 설정 (IAM Role 사용 시 불필요)
    ACCESS_KEY_ID: Optional[str] = None
    SECRET_ACCESS_KEY: Optional[str] = None
    PROFILE: Optional[str] = None  # AWS Profile (로컬 개발용)


class InternalSettings(BaseModel):
    """내부 식별자 설정"""
    AGENT_ID: str = "local-content-ai-agent-v1"
