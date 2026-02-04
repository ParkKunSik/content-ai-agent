import pytest
import logging
from src.services.es_content_retrieval_service import ESContentRetrievalService
from src.schemas.enums.content_type import ExternalContentType
from src.core.elasticsearch_config import es_manager, ElasticsearchConfig
from src.core.config import settings

# 로그 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_get_project_contents_real_data():
    """
    실제 ES 데이터를 조회하여 Project 365330의 리뷰 갯수를 확인하는 테스트
    """
    # 1. ES Manager 초기화
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
    
    try:
        es_manager.initialize(reference_config, main_config)
    except Exception as e:
        logger.warning(f"ES Manager initialization info: {e}")

    # 2. 서비스 인스턴스 생성
    service = ESContentRetrievalService()
    project_id = 365330
    
    # 3. 데이터 조회 (ExternalContentType.REVIEW 사용)
    # REVIEW 타입은 내부적으로 REVIEW와 PHOTO_REVIEW를 모두 포함함
    logger.info(f"프로젝트 {project_id}의 콘텐츠 조회를 시작합니다. (Type: REVIEW)")
    contents = await service.get_project_contents(
        project_id=project_id,
        content_type=ExternalContentType.REVIEW,
        size=5000  # 전체 데이터를 가져오기 위해 충분한 사이즈 설정
    )
    
    # 4. 타입별 갯수 계산
    # ESContentRetrievalService는 PHOTO_REVIEW인 경우에만 has_image=True로 설정함
    total_count = len(contents)
    photo_review_count = sum(1 for item in contents if item.has_image is True)
    review_count = total_count - photo_review_count
    
    # 5. 결과 출력
    print("\n" + "="*60)
    print(f"🔍 [실제 데이터 조회 결과] Project ID: {project_id}")
    print(f"  - 조회 후 전체 갯수: {total_count:,}개")
    print(f"  - InternalContentType.REVIEW 갯수: {review_count:,}개")
    print(f"  - InternalContentType.PHOTO_REVIEW 갯수: {photo_review_count:,}개")
    print("="*60)
    
    # 검증
    assert total_count > 0, f"프로젝트 {project_id}에서 조회된 데이터가 없습니다."
    assert photo_review_count > 0, "PHOTO_REVIEW 데이터가 1개 이상 존재해야 합니다."
    assert review_count > 0, "REVIEW 데이터가 1개 이상 존재해야 합니다."
