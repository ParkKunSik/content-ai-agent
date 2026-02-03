from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ElasticsearchConfig:
    """Elasticsearch 연결 설정"""
    host: str
    port: Optional[int] = 9200
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: bool = True
    verify_certs: bool = True
    timeout: int = 30


class ElasticsearchManager:
    """Elasticsearch 연결 관리자"""
    
    def __init__(self):
        self._reference_client: Optional['Elasticsearch'] = None
        self._main_client: Optional['Elasticsearch'] = None
    
    def initialize(self, reference_config: ElasticsearchConfig, main_config: ElasticsearchConfig):
        """ES 클라이언트 초기화"""
        try:
            from elasticsearch import Elasticsearch

            # 호스트 URL 구성 헬퍼 함수
            def build_host_url(config: ElasticsearchConfig) -> str:
                """호스트 URL 구성 (http:// 또는 https://가 포함된 경우 포트 생략)"""
                host = config.host.rstrip('/')
                # URL 형태인 경우 (http:// 또는 https://로 시작)
                if host.startswith('http://') or host.startswith('https://'):
                    return host
                # 일반 호스트명인 경우 포트 포함
                return f"{host}:{config.port}"

            # 참조용 클라이언트 (기존 wadiz 데이터 조회)
            # ES 8.x 서버와의 호환성을 위해 headers에 compatible-with=8 설정
            self._reference_client = Elasticsearch(
                hosts=[build_host_url(reference_config)],
                basic_auth=(reference_config.username, reference_config.password) if reference_config.username else None,
                verify_certs=reference_config.verify_certs,
                request_timeout=reference_config.timeout,
                headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8"}
            )

            # 메인 클라이언트 (분석 결과 저장)
            self._main_client = Elasticsearch(
                hosts=[build_host_url(main_config)],
                basic_auth=(main_config.username, main_config.password) if main_config.username else None,
                verify_certs=main_config.verify_certs,
                request_timeout=main_config.timeout,
                headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8"}
            )
            
            # 연결 테스트 (ping 대신 info() 사용 - 더 안정적)
            try:
                ref_info = self._reference_client.info()
                logger.info(f"Reference ES connected: {ref_info['cluster_name']}")
            except Exception as e:
                logger.error(f"Reference ES connection test failed: {e}")
                raise ConnectionError(f"Reference ES cluster connection failed: {e}")

            try:
                main_info = self._main_client.info()
                logger.info(f"Main ES connected: {main_info['cluster_name']}")
            except Exception as e:
                logger.warning(f"Main ES connection test failed: {e} (메인 ES는 선택적)")
                # 메인 ES는 선택적이므로 실패해도 계속 진행
                
            logger.info("Elasticsearch clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch clients: {e}")
            raise
    
    @property
    def reference_client(self) -> 'Elasticsearch':
        """참조용 클라이언트 반환 (기존 wadiz 데이터 조회)"""
        if not self._reference_client:
            raise RuntimeError("Elasticsearch reference client not initialized")
        return self._reference_client
    
    @property  
    def main_client(self) -> 'Elasticsearch':
        """메인 클라이언트 반환 (분석 결과 저장)"""
        if not self._main_client:
            raise RuntimeError("Elasticsearch main client not initialized")
        return self._main_client


# 싱글톤 인스턴스
es_manager = ElasticsearchManager()