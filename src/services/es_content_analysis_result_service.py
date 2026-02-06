import logging
from datetime import datetime, timezone
from typing import Optional

from elasticsearch import Elasticsearch

from src.core.config import settings
from src.core.elasticsearch_config import es_manager
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.es.content_analysis_result import (
    ContentAnalysisResultDataV1,
    ContentAnalysisResultDocument,
    ContentAnalysisResultState,
)
from src.schemas.models.prompt.structured_analysis_refined_response import StructuredAnalysisRefinedResponse
from src.schemas.models.prompt.structured_analysis_response import StructuredAnalysisResponse

logger = logging.getLogger(__name__)

class ESContentAnalysisResultService:
    """Elasticsearch 기반 분석 결과 저장 및 조회 서비스"""
    
    def __init__(self):
        self.client: Elasticsearch = es_manager.main_client
        self.index_name = settings.CONTENT_ANALYSIS_RESULT_INDEX
    
    def ensure_index_exists(self):
        """인덱스가 없으면 생성"""
        if not self.client.indices.exists(index=self.index_name):
            mappings = ContentAnalysisResultDocument.get_es_mapping()
            self.client.indices.create(index=self.index_name, body=mappings)
            logger.info(f"Created index: {self.index_name}")

    def _generate_doc_id(self, project_id: str, content_type: ExternalContentType, version: int) -> str:
        """문서 ID 생성 (멱등성 보장)"""
        return f"{project_id}_{content_type.value}_v{version}"

    async def get_result(
        self, 
        project_id: str, 
        content_type: ExternalContentType
    ) -> Optional[ContentAnalysisResultDocument]:
        """
        최신 분석 결과 조회 (가장 높은 버전)
        """
        try:
            query = {
                "bool": {
                    "must": [
                        {"term": {"project_id": project_id}},
                        {"term": {"content_type": content_type.value}}
                    ]
                }
            }
            
            response = self.client.search(
                index=self.index_name,
                query=query,
                sort=[{"version": {"order": "desc"}}],
                size=1
            )
            
            if response["hits"]["hits"]:
                source = response["hits"]["hits"][0]["_source"]
                return ContentAnalysisResultDocument(**source)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get result: {e}")
            return None

    async def get_next_version(self, project_id: str, content_type: ExternalContentType) -> int:
        """다음 버전 번호 조회"""
        current_doc = await self.get_result(project_id, content_type)
        if current_doc:
            return current_doc.version + 1
        return 1

    async def save_result(self, document: ContentAnalysisResultDocument) -> str:
        """분석 결과 저장 (새 버전 생성)"""
        try:
            self.ensure_index_exists()
            
            # 문서 ID 생성
            doc_id = self._generate_doc_id(
                document.project_id, 
                document.content_type, 
                document.version
            )
            
            # 저장
            self.client.index(
                index=self.index_name,
                id=doc_id,
                document=document.model_dump(mode='json'),
                refresh=True # 테스트를 위해 즉시 반영
            )
            
            logger.info(f"Saved result: {doc_id} (State: {document.state})")
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to save result: {e}")
            raise

    async def save_analysis_result(
        self,
        project_id: str,
        project_type: ProjectType,
        content_type: ExternalContentType,
        version: int,
        state: ContentAnalysisResultState,
        structured_response: StructuredAnalysisResponse,
        persona: PersonaType = PersonaType.PRO_DATA_ANALYST,
        refine_persona: Optional[PersonaType] = None,
        refined_summary: Optional[StructuredAnalysisRefinedResponse] = None,
        reason: str = None
    ) -> str:
        """구조화된 분석 응답을 V1 형식으로 저장하는 헬퍼 메서드"""
        
        # V1 결과 데이터 생성
        result_data = ContentAnalysisResultDataV1(
            persona=persona,
            data=structured_response,
            refine_persona=refine_persona,
            refined_summary=refined_summary
        )
        
        # 문서 생성
        document = ContentAnalysisResultDocument(
            project_id=project_id,
            project_type=project_type,
            content_type=content_type,
            version=version,
            state=state,
            reason=reason,
            result=result_data
        )
        
        return await self.save_result(document)

    async def update_state(
        self, 
        project_id: str, 
        content_type: ExternalContentType, 
        version: int,
        state: ContentAnalysisResultState,
        reason: str = None
    ):
        """특정 버전의 상태 업데이트"""
        try:
            doc_id = self._generate_doc_id(project_id, content_type, version)
            
            update_body = {
                "doc": {
                    "state": state,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
            if reason:
                update_body["doc"]["reason"] = reason
                
            self.client.update(
                index=self.index_name,
                id=doc_id,
                body=update_body,
                refresh=True
            )
            logger.info(f"Updated state for {doc_id} to {state}")
            
        except Exception as e:
            logger.error(f"Failed to update state: {e}")
            raise
