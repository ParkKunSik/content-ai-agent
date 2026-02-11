"""Viewer 설정 - ES 연결 정보만 관리"""

import logging
from typing import Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env 파일 로드
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("viewer.config")


class Settings(BaseSettings):
    """Viewer 설정 (ES 연결 정보)"""

    # 서버 설정
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8787

    # ES 설정
    ES_HOST: str = "localhost"
    ES_PORT: Optional[int] = None  # 포트 없으면 None (기본 포트 사용)
    ES_USERNAME: Optional[str] = None
    ES_PASSWORD: Optional[str] = None
    ES_USE_SSL: bool = False
    ES_VERIFY_CERTS: bool = False
    ES_TIMEOUT: int = 30
    ES_INDEX: str = "core-content-analysis-result"

    @field_validator('ES_PORT', mode='before')
    @classmethod
    def validate_port(cls, v):
        """빈 문자열을 None으로 변환"""
        if v == '' or v is None:
            return None
        return int(v)

    # Wadiz API (프로젝트 정보 조회용)
    WADIZ_API_BASE_URL: str = "https://www.wadiz.kr"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
logger.info(f"Viewer Config - ES Host: {settings.ES_HOST}, Port: {settings.ES_PORT}")
