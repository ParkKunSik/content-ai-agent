"""
뷰어 전용 Elasticsearch 클라이언트

기존 es_manager와 완전히 독립적으로 동작:
- es_manager: reference + main 클라이언트 (Orchestrator 초기화 필요)
- ViewerESClient: main 클라이언트만 (자체 초기화)
"""
import logging

from elasticsearch import Elasticsearch

from src.core.config import settings

logger = logging.getLogger(__name__)


class ViewerESClient:
    """
    뷰어 전용 Elasticsearch 클라이언트 (싱글톤)

    Main ES 클러스터에만 연결하며, 분석 결과 조회 전용으로 사용됩니다.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialize()
        self._initialized = True

    def _initialize(self):
        """자체 ES 클라이언트 초기화"""
        host = settings.ES_MAIN_HOST
        port = settings.ES_MAIN_PORT

        # URL 형태 처리 (http:// 또는 https://로 시작하는 경우)
        if host.startswith("http://") or host.startswith("https://"):
            hosts = [host]
        else:
            hosts = [f"{host}:{port}"]

        logger.info(f"ViewerESClient: Connecting to {hosts}")

        self.client = Elasticsearch(
            hosts=hosts,
            basic_auth=(settings.ES_MAIN_USERNAME, settings.ES_MAIN_PASSWORD)
            if settings.ES_MAIN_USERNAME
            else None,
            verify_certs=settings.ES_MAIN_VERIFY_CERTS,
            request_timeout=settings.ES_MAIN_TIMEOUT,
            headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8"},
        )
        self.index_name = settings.CONTENT_ANALYSIS_RESULT_INDEX

        # 연결 테스트
        try:
            info = self.client.info()
            logger.info(f"ViewerESClient: Connected to {info['cluster_name']}")
        except Exception as e:
            logger.error(f"ViewerESClient: Connection failed - {e}")
            raise ConnectionError(f"Failed to connect to ES: {e}")

    def ping(self) -> bool:
        """ES 연결 상태 확인"""
        try:
            return self.client.ping()
        except Exception:
            return False
