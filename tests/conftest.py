import logging
import os
import sys

import pytest
from dotenv import load_dotenv

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 환경 변수 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)

from src.core.config import settings
from src.core.elasticsearch_config import ElasticsearchConfig, es_manager
from src.core.session_factory import SessionFactory
from src.services.llm_service import LLMService
from src.utils.prompt_manager import PromptManager
from tests.data.test_contents import MILD_NEGATIVE_CONTENT, NEGATIVE_CONTENT_QUALITY, POSITIVE_CONTENT, TOXIC_CONTENT


# 로깅 필터 설정
class VertexLogFilter(logging.Filter):
    def filter(self, record):
        return "REST async clients requires async credentials" not in record.getMessage()

logging.basicConfig(level=logging.INFO)
logging.getLogger("").addFilter(VertexLogFilter())

def get_sample_contents():
    return [POSITIVE_CONTENT, NEGATIVE_CONTENT_QUALITY, MILD_NEGATIVE_CONTENT, TOXIC_CONTENT]

@pytest.fixture(scope="function", autouse=True)
def setup_session_factory():
    print("\n🔧 SessionFactory 초기화 중 (Function Scope)...")
    SessionFactory.initialize()
    print("✅ SessionFactory 초기화 완료")

@pytest.fixture(scope="session")
def setup_elasticsearch():
    """ES 매니저 초기화 (세션 스코프 - 테스트 세션당 1회)"""
    try:
        # ES 매니저가 이미 초기화되었는지 확인
        _ = es_manager.reference_client
        print("🔗 ES manager already initialized")
    except RuntimeError:
        # 초기화되지 않은 경우 초기화 수행
        print("🔧 ES manager 초기화 중...")
        reference_config = ElasticsearchConfig(
            host=settings.ES_REFERENCE_HOST,
            port=settings.ES_REFERENCE_PORT,
            username=settings.ES_REFERENCE_USERNAME,
            password=settings.ES_REFERENCE_PASSWORD,
            use_ssl=settings.ES_REFERENCE_USE_SSL,
            verify_certs=settings.ES_REFERENCE_VERIFY_CERTS,
            timeout=settings.ES_REFERENCE_TIMEOUT
        )
        
        main_config = ElasticsearchConfig(
            host=settings.ES_MAIN_HOST,
            port=settings.ES_MAIN_PORT,
            username=settings.ES_MAIN_USERNAME,
            password=settings.ES_MAIN_PASSWORD,
            use_ssl=settings.ES_MAIN_USE_SSL,
            verify_certs=settings.ES_MAIN_VERIFY_CERTS,
            timeout=settings.ES_MAIN_TIMEOUT
        )
        
        es_manager.initialize(reference_config, main_config)
        print("✅ ES manager 초기화 완료")
    
    return es_manager

@pytest.fixture
def llm_service():
    return LLMService(PromptManager())

@pytest.fixture
def sample_contents():
    return get_sample_contents()

@pytest.fixture(autouse=True)
def cleanup_resources():
    yield
    import gc
    import time
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        warnings.simplefilter("ignore", UserWarning)
        time.sleep(0.1)
        gc.collect()
