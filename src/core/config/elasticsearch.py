"""Elasticsearch 설정"""

from typing import Optional
from pydantic import BaseModel, field_validator


class ESClusterSettings(BaseModel):
    """ES 클러스터 연결 설정"""
    HOST: str = "localhost"
    PORT: Optional[int] = 9200
    USERNAME: Optional[str] = None
    PASSWORD: Optional[str] = None
    USE_SSL: bool = False
    VERIFY_CERTS: bool = False
    TIMEOUT: int = 30

    @field_validator('PORT', mode='before')
    @classmethod
    def validate_port(cls, v):
        """빈 문자열을 None으로 변환"""
        if v == '' or v is None:
            return None
        return int(v)


class ESIndexSettings(BaseModel):
    """ES 인덱스/Alias 설정"""
    # 기본 인덱스 (하위 호환)
    DEFAULT_INDEX: str = "core-content-analysis-result"
    DEFAULT_ALIAS: str = "core-content-analysis-result-alias"

    # Provider별 인덱스
    VERTEX_AI_INDEX: str = "core-content-analysis-result-vertex-ai"
    VERTEX_AI_ALIAS: str = "core-content-analysis-result-vertex-ai-alias"
    OPENAI_INDEX: str = "core-content-analysis-result-openai"
    OPENAI_ALIAS: str = "core-content-analysis-result-openai-alias"
    GEMINI_API_INDEX: str = "core-content-analysis-result-gemini-api"
    GEMINI_API_ALIAS: str = "core-content-analysis-result-gemini-api-alias"

    # 기본 인덱스 사용 여부
    USE_DEFAULT: bool = True


class ElasticsearchSettings(BaseModel):
    """Elasticsearch 통합 설정"""
    REFERENCE: ESClusterSettings = ESClusterSettings()  # 기존 wadiz 데이터 조회
    MAIN: ESClusterSettings = ESClusterSettings(PORT=9201)  # 분석 결과 저장
    INDEX: ESIndexSettings = ESIndexSettings()
