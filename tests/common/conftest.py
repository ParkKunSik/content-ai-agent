import pytest
import logging
import sys
import os
from dotenv import load_dotenv

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 환경 변수 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)

from src.services.llm_service import LLMService
from src.utils.prompt_manager import PromptManager
from src.core.session_factory import SessionFactory
from tests.data.test_contents import POSITIVE_CONTENT, NEGATIVE_CONTENT_QUALITY, MILD_NEGATIVE_CONTENT, TOXIC_CONTENT

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

@pytest.fixture
def llm_service():
    return LLMService(PromptManager())

@pytest.fixture
def sample_contents():
    return get_sample_contents()

@pytest.fixture(autouse=True)
def cleanup_resources():
    yield
    import time
    import gc
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        warnings.simplefilter("ignore", UserWarning)
        time.sleep(0.1)
        gc.collect()
