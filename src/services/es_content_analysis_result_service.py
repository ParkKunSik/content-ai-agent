import json
import logging
from datetime import datetime, timezone
from typing import Optional

from elasticsearch import Elasticsearch

from src.core.config import settings
from src.core.elasticsearch_config import es_manager
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.structured_analysis_refine_result import StructuredAnalysisRefineResult
from src.schemas.models.es.content_analysis_result import (
    ContentAnalysisResultDataV1,
    ContentAnalysisResultDocument,
    ContentAnalysisResultState,
)
from src.schemas.models.prompt.structured_analysis_result import StructuredAnalysisResult

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

    def _generate_doc_id(self, project_id: str, project_type: ProjectType, content_type: ExternalContentType) -> str:
        """문서 ID 생성 (프로젝트+타입 조합으로 고유성 보장)"""
        return f"{project_id}_{project_type.value}_{content_type.value}"

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
        """분석 결과 저장 (동일 프로젝트/타입 조합은 덮어쓰기됨)"""
        doc_id = None
        try:
            self.ensure_index_exists()
            
            # 문서 ID 생성 (version 제외)
            doc_id = self._generate_doc_id(
                document.project_id, 
                document.project_type,
                document.content_type
            )
            
            # Pydantic V2의 model_dump_json()을 사용하여 직렬화 안정성 확보
            doc_dict = json.loads(document.model_dump_json())
            
            logger.info(f"Indexing document to ES: {doc_id} in index {self.index_name}")
            
            # 저장
            response = self.client.index(
                index=self.index_name,
                id=doc_id,
                document=doc_dict,
                refresh=True
            )
            
            es_result = response.get('result')
            logger.info(f"ES Save Result: {es_result} for doc_id: {doc_id}")
            
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to save result to ES (doc_id: {doc_id if 'doc_id' in locals() else 'unknown'}): {e}")
            if hasattr(e, 'info'):
                logger.error(f"ES Error Detailed Info: {e.info}")
            raise

    async def save_analysis_result(
        self,
        project_id: str,
        project_type: ProjectType,
        content_type: ExternalContentType,
        version: int,
        state: ContentAnalysisResultState,
        structured_response: StructuredAnalysisResult,
        refine_persona: PersonaType,
        refined_result: StructuredAnalysisRefineResult,
        persona: PersonaType = PersonaType.PRO_DATA_ANALYST,
        reason: str = None
    ) -> str:
        """구조화된 분석 응답을 V1 형식으로 저장하는 헬퍼 메서드"""
        
        # V1 결과 데이터 생성
        result_data = ContentAnalysisResultDataV1(
            meta_persona=persona,
            meta_data=structured_response,
            persona=refine_persona,
            data=refined_result
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
        project_type: ProjectType,
        content_type: ExternalContentType, 
        state: ContentAnalysisResultState,
        reason: str = None
    ):
        """특정 프로젝트 분석 결과의 상태 업데이트"""
        try:
            doc_id = self._generate_doc_id(project_id, project_type, content_type)
            
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