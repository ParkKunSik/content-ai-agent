import json
import logging
from datetime import datetime, timezone
from typing import Optional

from elasticsearch import Elasticsearch

from src.core.config import settings
from src.core.elasticsearch_config import es_manager
from src.core.llm.enums import ProviderType
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.es.content_analysis_result import (
    ContentAnalysisResultDocument,
    ContentAnalysisResultState,
)

logger = logging.getLogger(__name__)


class ESContentAnalysisResultService:
    """Elasticsearch 기반 분석 결과 저장 및 조회 서비스"""

    def __init__(self):
        self.client: Elasticsearch = es_manager.main_client

        # 기존 설정 (하위 호환)
        self.result_index_name = settings.ANALYSIS_RESULT_INDEX
        self.result_index_alias = settings.ANALYSIS_RESULT_ALIAS

        # Provider별 설정
        self._provider_config = {
            ProviderType.VERTEX_AI: {
                "index": settings.ANALYSIS_RESULT_VERTEX_AI_INDEX,
                "alias": settings.ANALYSIS_RESULT_VERTEX_AI_ALIAS,
            },
            ProviderType.OPENAI: {
                "index": settings.ANALYSIS_RESULT_OPENAI_INDEX,
                "alias": settings.ANALYSIS_RESULT_OPENAI_ALIAS,
            },
        }

        # 기존 alias 초기화
        self._ensure_alias_exists(self.result_index_name, self.result_index_alias)

        # Provider별 alias 초기화
        for provider_type, config in self._provider_config.items():
            try:
                self._ensure_alias_exists(config["index"], config["alias"])
            except Exception as e:
                logger.warning(f"Failed to initialize alias for {provider_type.name}: {e}")

    # ========================================================================
    # Private Methods (alias 파라미터 필수)
    # ========================================================================

    def _ensure_alias_exists(self, index_name: str, alias_name: str) -> None:
        """인덱스와 Alias가 없으면 생성 후 연결"""
        # 1. Alias 존재 여부 확인 (있으면 index도 존재한다고 간주)
        if self.client.indices.exists_alias(name=alias_name):
            logger.debug(f"Alias already exists: {alias_name}")
            return

        # 2. 인덱스 존재 여부 확인 및 생성
        if not self.client.indices.exists(index=index_name):
            mappings = ContentAnalysisResultDocument.get_es_mapping()
            self.client.indices.create(index=index_name, body=mappings)
            logger.info(f"Created index: {index_name}")

        # 3. Alias 생성
        self.client.indices.put_alias(index=index_name, name=alias_name)
        logger.info(f"Created alias: {alias_name} -> {index_name}")

    def _get_alias_for_provider(self, provider_type: ProviderType) -> str:
        """Provider 타입에 따른 alias 반환"""
        if not settings.USE_DEFAULT_ES_INDEX:
            config = self._provider_config.get(provider_type)
            if config:
                return config["alias"]
        return self.result_index_alias

    def _get_index_for_provider(self, provider_type: ProviderType) -> str:
        """Provider 타입에 따른 index 반환"""
        if not settings.USE_DEFAULT_ES_INDEX:
            config = self._provider_config.get(provider_type)
            if config:
                return config["index"]
        return self.result_index_name

    def _generate_doc_id(
        self, project_id: str, project_type: ProjectType, content_type: ExternalContentType
    ) -> str:
        """문서 ID 생성 (프로젝트+타입 조합으로 고유성 보장)"""
        return f"{project_id}_{project_type.value}_{content_type.value}"

    async def _get_result(
        self,
        project_id: str,
        content_type: ExternalContentType,
        alias: str
    ) -> Optional[ContentAnalysisResultDocument]:
        """최신 분석 결과 조회 (가장 높은 버전)"""
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
                index=alias,
                query=query,
                sort=[{"version": {"order": "desc"}}],
                size=1
            )

            if response["hits"]["hits"]:
                source = response["hits"]["hits"][0]["_source"]
                return ContentAnalysisResultDocument(**source)
            return None

        except Exception as e:
            logger.error(f"Failed to get result from {alias}: {e}")
            return None

    async def _get_next_version(
        self,
        project_id: str,
        content_type: ExternalContentType,
        alias: str
    ) -> int:
        """다음 버전 번호 조회"""
        current_doc = await self._get_result(project_id, content_type, alias)
        if current_doc:
            return current_doc.version + 1
        return 1

    async def _save_result(
        self,
        document: ContentAnalysisResultDocument,
        alias: str
    ) -> str:
        """분석 결과 저장"""
        doc_id = None
        try:
            doc_id = self._generate_doc_id(
                document.project_id,
                document.project_type,
                document.content_type
            )

            doc_dict = json.loads(document.model_dump_json())

            logger.info(f"Indexing document to ES: {doc_id} in alias {alias}")

            response = self.client.index(
                index=alias,
                id=doc_id,
                document=doc_dict,
                refresh=True
            )

            es_result = response.get('result')
            logger.info(f"ES Save Result: {es_result} for doc_id: {doc_id}")

            return doc_id

        except Exception as e:
            logger.error(f"Failed to save result to ES (doc_id: {doc_id or 'unknown'}): {e}")
            if hasattr(e, 'info'):
                logger.error(f"ES Error Detailed Info: {e.info}")
            raise

    async def _update_state(
        self,
        project_id: str,
        project_type: ProjectType,
        content_type: ExternalContentType,
        state: ContentAnalysisResultState,
        alias: str,
        reason: str = None
    ) -> None:
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
                index=alias,
                id=doc_id,
                body=update_body,
                refresh=True
            )
            logger.info(f"Updated state for {doc_id} to {state}")

        except Exception as e:
            logger.error(f"Failed to update state: {e}")
            raise

    # ========================================================================
    # Public Methods (Provider별)
    # ========================================================================

    async def get_result_by_provider(
        self,
        project_id: str,
        content_type: ExternalContentType,
        provider_type: ProviderType
    ) -> Optional[ContentAnalysisResultDocument]:
        """최신 분석 결과 조회 (Provider별 alias 사용)"""
        alias = self._get_alias_for_provider(provider_type)
        return await self._get_result(project_id, content_type, alias)

    async def get_next_version_by_provider(
        self,
        project_id: str,
        content_type: ExternalContentType,
        provider_type: ProviderType
    ) -> int:
        """다음 버전 번호 조회 (Provider별 alias 사용)"""
        alias = self._get_alias_for_provider(provider_type)
        return await self._get_next_version(project_id, content_type, alias)

    async def save_result_by_provider(
        self,
        document: ContentAnalysisResultDocument,
        provider_type: ProviderType
    ) -> str:
        """분석 결과 저장 (Provider별 alias 사용)"""
        alias = self._get_alias_for_provider(provider_type)
        return await self._save_result(document, alias)

    async def update_state_by_provider(
        self,
        project_id: str,
        project_type: ProjectType,
        content_type: ExternalContentType,
        state: ContentAnalysisResultState,
        provider_type: ProviderType,
        reason: str = None
    ) -> None:
        """특정 프로젝트 분석 결과의 상태 업데이트 (Provider별 alias 사용)"""
        alias = self._get_alias_for_provider(provider_type)
        await self._update_state(
            project_id, project_type, content_type, state, alias, reason
        )
