import logging
from typing import List

from elasticsearch import Elasticsearch

from src.core.elasticsearch_config import es_manager
from src.schemas.enums.content_type import ExternalContentType, InternalContentType
from src.schemas.models.common.content_item import ContentItem

logger = logging.getLogger(__name__)

class ESContentRetrievalService:
    """Elasticsearch 기반 프로젝트 콘텐츠 조회 서비스"""
    
    def __init__(self):
        # 참조용 ES 클라이언트 사용 (기존 데이터 조회)
        self.client: Elasticsearch = es_manager.reference_client
    
    async def get_funding_preorder_project_contents(
        self, 
        project_id: int, 
        content_type: ExternalContentType,
        size: int = 1000,
        from_: int = 0
    ) -> List[ContentItem]:
        """
        프로젝트 콘텐츠 조회 후 ContentItem 리스트 반환
        
        Args:
            project_id: 프로젝트 ID (캠페인 ID)
            content_type: 외부 콘텐츠 타입
            size: 조회할 문서 수
            from_: 시작 위치
            
        Returns:
            List[ContentItem]: 콘텐츠 아이템 리스트
        """
        try:
            # 1. 외부 타입을 내부 타입으로 변환
            internal_types = content_type.to_internal()
            
            # 2. 인덱스 패턴 가져오기 (첫 번째 내부 타입 기준)
            # 모든 내부 타입이 같은 인덱스 패턴을 공유한다고 가정 (현재는 g2/g4 분리되어 있지만 ExternalContentType 정의상 섞이지 않음)
            # 만약 섞인다면 별도 처리 필요하지만, 현재 정의된 ExternalContentType은 호환되는 내부 타입끼리 묶여 있음
            index_pattern = internal_types[0].index_pattern
            
            # 3. ES 쿼리 조건 생성
            query = InternalContentType.get_combined_query_conditions(
                internal_types, project_id
            )
            
            logger.info(f"Executing ES search on {index_pattern} with query: {query}")
            
            # 4. ES 조회 실행
            # 비동기 클라이언트가 아니므로 동기 호출 (FastAPI async def 내에서 실행되므로 스레드 풀에서 실행됨)
            # elasticsearch-py의 AsyncElasticsearch를 사용하지 않고 동기 클라이언트를 사용 중이므로,
            # 대량 조회 시 블로킹 가능성 있음. 하지만 현재 구조상 허용.
            response = self.client.search(
                index=index_pattern,
                body={
                    "query": query,
                    "size": size,
                    "from": from_,
                    "sort": [{"seq": {"order": "asc"}}],  # seq 필드로 정렬
                    "_source": [
                        "seq",           # → id로 매핑
                        "body",          # → content로 매핑
                        "groupsubcode",  # has_image 판단용
                        "campaignid", 
                        "created_at"
                    ]
                }
            )
            
            # 5. ContentItem 리스트로 변환
            hits = response["hits"]["hits"]
            logger.info(f"ES response hits count: {len(hits)}")
            if hits:
                logger.info(f"Sample hit source keys: {hits[0]['_source'].keys()}")
            
            content_items = []
            
            for hit in hits:
                source = hit["_source"]
                
                # ES 필드 매핑
                # seq는 integer로 가정. 없으면 0 또는 예외 처리?
                # ContentItem.content_id는 int 필수.
                seq_val = source.get("seq")
                if seq_val is None:
                    # seq가 없으면 _id를 시도하되, int 변환 가능해야 함
                    try:
                        content_id = int(hit["_id"])
                    except (ValueError, TypeError):
                        logger.warning(f"Skipping document without valid seq or numeric _id: {hit['_id']}")
                        continue
                else:
                    content_id = int(seq_val)

                content_text = source.get("body", "")
                groupsubcode = source.get("groupsubcode", "")
                
                # 빈 콘텐츠 제외
                if content_text and content_text.strip():
                    content_item = ContentItem(
                        content_id=content_id,
                        content=content_text.strip(),
                        has_image=(groupsubcode == "PHOTO_REVIEW")
                    )
                    content_items.append(content_item)
            
            logger.info(
                f"Retrieved {len(content_items)} valid contents for project {project_id}, "
                f"type {content_type.value} from {index_pattern} "
                f"(total hits: {response['hits']['total']['value']})"
            )
            
            return content_items
            
        except Exception as e:
            logger.error(f"Failed to retrieve contents for project {project_id}: {e}")
            raise RuntimeError(f"ES content retrieval failed: {e}")
