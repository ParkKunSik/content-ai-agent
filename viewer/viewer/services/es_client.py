"""Elasticsearch 클라이언트"""

import logging
import sys
import warnings
from pathlib import Path
from typing import Optional

# ES TLS 경고 숨김 (verify_certs=False 사용 시)
warnings.filterwarnings("ignore", message=".*verify_certs=False.*")

# viewer 패키지 경로를 sys.path에 추가
_viewer_root = Path(__file__).parent.parent.parent
if str(_viewer_root) not in sys.path:
    sys.path.insert(0, str(_viewer_root))

from elasticsearch import Elasticsearch

from viewer.config import settings

logger = logging.getLogger(__name__)


class ESClient:
    """Viewer용 ES 클라이언트 (싱글톤)"""

    _instance: Optional["ESClient"] = None
    _client: Optional[Elasticsearch] = None

    def __new__(cls) -> "ESClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is not None:
            return

        host = settings.ES_HOST.rstrip("/")  # 끝 슬래시 제거
        port = settings.ES_PORT

        # URL 구성 (host에 프로토콜이 포함된 경우 처리)
        if host.startswith("http://") or host.startswith("https://"):
            # 프로토콜이 이미 포함된 경우
            if port:
                es_url = f"{host}:{port}"
            else:
                es_url = host
        else:
            # 프로토콜이 없는 경우
            scheme = "https" if settings.ES_USE_SSL else "http"
            if port:
                es_url = f"{scheme}://{host}:{port}"
            else:
                es_url = f"{scheme}://{host}"

        logger.info(f"Connecting to ES: {es_url}")

        self._client = Elasticsearch(
            es_url,
            basic_auth=(settings.ES_USERNAME, settings.ES_PASSWORD)
            if settings.ES_USERNAME
            else None,
            verify_certs=settings.ES_VERIFY_CERTS,
            request_timeout=settings.ES_TIMEOUT,
        )

        # 연결 테스트
        if self._client.ping():
            logger.info("ES connection successful")
        else:
            logger.warning("ES ping failed")

    @property
    def client(self) -> Elasticsearch:
        """ES 클라이언트 반환"""
        if self._client is None:
            raise RuntimeError("ES client not initialized")
        return self._client

    @property
    def result_index_alias(self) -> str:
        """분석 결과 Alias 이름"""
        return settings.ES_ANALYSIS_RESULT_ALIAS

    def get_alias_for_provider(self, provider: str) -> str:
        """Provider 문자열에 따른 alias 반환

        Args:
            provider: "vertex-ai" 또는 "openai"

        Returns:
            해당 provider의 alias, 미지원 provider면 기존 alias 반환
        """
        if provider == "vertex-ai":
            return settings.ES_VERTEX_AI_ALIAS
        elif provider == "openai":
            return settings.ES_OPENAI_ALIAS
        return settings.ES_ANALYSIS_RESULT_ALIAS
