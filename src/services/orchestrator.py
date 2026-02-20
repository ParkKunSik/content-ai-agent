import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from src.core.config import settings
from src.core.elasticsearch_config import ElasticsearchConfig, es_manager
from src.core.llm.enums import ProviderType
from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.common.llm_usage_info import LLMUsageInfo
from src.schemas.models.common.structured_analysis_refine_result import (
    RefineCategoryItem,
    RefineHighlightItem,
    StructuredAnalysisRefineResult,
)
from src.schemas.models.es.content_analysis_result import (
    ContentAnalysisResultDataV1,
    ContentAnalysisResultDocument,
    ContentAnalysisResultState,
)
from src.schemas.models.prompt.structured_analysis_summary import CategorySummaryItem, StructuredAnalysisSummary
from src.services.es_content_analysis_result_service import ESContentAnalysisResultService
from src.services.es_content_retrieval_service import ESContentRetrievalService
from src.services.llm_service import LLMService
from src.services.request_content_loader import RequestContentLoader
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Coordinates the analysis process by delegating tasks to Specialized Services.
    """

    def __init__(self):
        # ES 매니저 초기화 (아직 초기화되지 않은 경우)
        self._ensure_es_manager_initialized()

        self.loader = RequestContentLoader()
        self.prompt_manager = PromptManager()
        self.llm_service = LLMService(self.prompt_manager)
        self.es_content_service = ESContentRetrievalService()
        self.es_result_service = ESContentAnalysisResultService()

    def _ensure_es_manager_initialized(self):
        """ES 매니저가 초기화되지 않은 경우 초기화"""
        try:
            # ES 매니저가 이미 초기화되었는지 확인
            _ = es_manager.reference_client
            logger.debug("ES manager already initialized")
        except RuntimeError:
            # 초기화되지 않은 경우 초기화 수행
            logger.info("Initializing ES manager...")
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
            logger.info("ES manager initialized successfully")

    def _get_current_provider_type(self) -> ProviderType:
        """현재 설정된 LLM Provider 타입 반환"""
        return settings.LLM_PROVIDER

    async def analysis(
        self,
        project_id: int,
        project_type: ProjectType,
        contents: List[ContentItem],
        analysis_mode: AnalysisMode,
        content_type: Optional[ExternalContentType] = None
    ) -> Tuple[ContentAnalysisResultDataV1, List[LLMUsageInfo]]:
        """
        Internal 2-step analysis logic.
        Returns ContentAnalysisResultDataV1 containing both raw and refined results,
        along with LLM usage information.

        Args:
            contents: List of ContentItem objects (content_id required for traceability)

        Returns:
            Tuple[ContentAnalysisResultDataV1, List[LLMUsageInfo]]: 분석 결과와 LLM 사용 정보 목록
        """
        logger.info(f"Executing core analysis for Project: {project_id}, Mode: {analysis_mode}, Content Type: {content_type}")

        llm_usages: List[LLMUsageInfo] = []

        # 1. Validate contents
        content_items = self._validate_contents(contents)

        # 2. Step 1: Main Analysis (PRO_DATA_ANALYST)
        logger.info("Executing Step 1: Main Analysis")
        base_analysis, structuring_usage = await self.llm_service.structure_content_analysis(
            project_id=project_id,
            project_type=project_type,
            content_items=content_items,
            content_type=content_type
        )
        llm_usages.append(structuring_usage)
        logger.info(f"Step 1 completed. Categories found: {len(base_analysis.categories)}, Duration: {structuring_usage.duration_ms}ms")

        # 3. Step 2: Refine Summary
        # Uses the persona defined in AnalysisMode for refinement
        logger.info(f"Executing Step 2: Refinement with persona {analysis_mode.persona_type}")

        # Step1 결과를 StructuredAnalysisSummary로 변환 (keywords, good_points, caution_points 포함)
        refine_content_items = StructuredAnalysisSummary(
            summary=base_analysis.summary,
            keywords=base_analysis.keywords,
            good_points=base_analysis.good_points,
            caution_points=base_analysis.caution_points,
            categories=[
                CategorySummaryItem(key=cat.key, summary=cat.summary, keywords=cat.keywords)
                for cat in base_analysis.categories
            ]
        )

        refinement_result, refining_usage = await self.llm_service.refine_analysis_summary(
            project_id=project_id,
            project_type=project_type,
            refine_content_items=refine_content_items,
            persona_type=analysis_mode.persona_type,
            content_type=content_type
        )
        llm_usages.append(refining_usage)
        logger.info(f"Step 2 completed. Duration: {refining_usage.duration_ms}ms")

        # 4. Construct Final Refined Result
        refined_categories = []
        # 정제된 카테고리 정보 맵 (summary, keywords 포함)
        refined_map = {
            cat.key: {"summary": cat.summary, "keywords": cat.keywords}
            for cat in refinement_result.categories
        }

        for base_cat in base_analysis.categories:
            # 정제된 요약/키워드가 있으면 사용, 없으면 원본 유지
            refined_data = refined_map.get(base_cat.key, {})
            final_summary = refined_data.get("summary", base_cat.summary)
            final_keywords = refined_data.get("keywords", base_cat.keywords)

            refine_highlights = [
                RefineHighlightItem(
                    id=h.id,
                    keyword=h.keyword,
                    highlight=h.highlight,
                    content=h.content
                ) for h in base_cat.highlights
            ]

            refined_categories.append(RefineCategoryItem(
                name=base_cat.name,
                key=base_cat.key,
                summary=final_summary,
                keywords=final_keywords,
                display_highlight=base_cat.display_highlight,
                sentiment_type=base_cat.sentiment_type,
                positive_count=len(base_cat.positive_contents),
                negative_count=len(base_cat.negative_contents),
                highlights=refine_highlights
            ))

        final_refined_result = StructuredAnalysisRefineResult(
            summary=refinement_result.summary,
            keywords=refinement_result.keywords,
            good_points=refinement_result.good_points,
            caution_points=refinement_result.caution_points,
            categories=refined_categories
        )

        # 5. Wrap into V1 Result Data object
        result_v1 = ContentAnalysisResultDataV1(
            meta_persona=PersonaType.PRO_DATA_ANALYST,
            meta_data=base_analysis,
            persona=analysis_mode.persona_type,
            data=final_refined_result
        )

        return result_v1, llm_usages

    async def funding_preorder_project_analysis(
        self,
        project_id: int,
        content_type: ExternalContentType,
        analysis_mode: AnalysisMode
    ) -> StructuredAnalysisRefineResult:
        return await self.project_analysis(project_id, ProjectType.FUNDING_AND_PREORDER, content_type, analysis_mode)

    async def project_analysis(
        self,
        project_id: int,
        project_type: ProjectType,
        content_type: ExternalContentType,
        analysis_mode: AnalysisMode
    ) -> StructuredAnalysisRefineResult:
        """
        Performs project-based analysis and saves the result to Elasticsearch.
        """
        logger.info(f"Starting project analysis for Project: {project_id}, Content Type: {content_type}, Mode: {analysis_mode}")

        # 1. ES에서 콘텐츠 조회
        logger.info(f"Retrieving content from ES for project {project_id}")
        content_items = await self.es_content_service.get_funding_preorder_project_contents(
            project_id=project_id,
            content_type=content_type
        )

        if not content_items:
            logger.warning(f"No content found for project {project_id} with content type {content_type}")
            raise ValueError(f"프로젝트 {project_id}의 {content_type} 콘텐츠를 찾을 수 없습니다.")

        logger.info(f"Retrieved {len(content_items)} content items from ES")

        # 2. baseline_content_id 선정
        baseline_content_id = self.select_baseline_content_id(content_items)
        logger.info(f"Selected baseline_content_id: {baseline_content_id}")

        # 3. 분석 수행
        result_v1, llm_usages = await self.analysis(
            project_id=project_id,
            project_type=project_type,
            contents=content_items,
            analysis_mode=analysis_mode,
            content_type=content_type
        )

        # 4. 분석 결과 저장 (프로젝트 분석 모드에서만 수행)
        try:
            # Provider 타입 결정
            provider_type = self._get_current_provider_type()
            logger.info(f"Saving analysis result to ES for project {project_id}, provider: {provider_type.name}")

            # 기존 문서 조회 (버전, created_at 유지용)
            existing_doc = await self.es_result_service.get_result_by_provider(
                str(project_id), content_type, provider_type
            )
            next_version = existing_doc.version + 1 if existing_doc else 1

            # 문서 생성 (기존 문서가 있으면 created_at 유지)
            document = ContentAnalysisResultDocument(
                project_id=str(project_id),
                project_type=project_type,
                content_type=content_type,
                version=next_version,
                state=ContentAnalysisResultState.COMPLETED,
                result=result_v1,
                llm_usages=llm_usages,
                baseline_content_id=baseline_content_id,
                created_at=existing_doc.created_at if existing_doc else datetime.now(timezone.utc)
            )

            # 저장 (Provider별)
            await self.es_result_service.save_result_by_provider(document, provider_type)
            logger.info(f"Successfully saved project analysis result (version: {next_version}, provider: {provider_type.name}, llm_usages: {len(llm_usages)})")
        except Exception as e:
            logger.error(f"Failed to save analysis result to ES: {e}")
            # 저장 실패가 사용자 응답을 방해하지 않도록 예외는 로깅만 수행

        logger.info(f"Project analysis completed for project {project_id}")

        return result_v1.data

    def _validate_contents(self, contents: List[ContentItem]) -> List[ContentItem]:
        """Validates ContentItem list and filters out invalid items."""
        validated = []
        for item in contents:
            if isinstance(item, ContentItem):
                if item.content and item.content.strip():
                    validated.append(item)
                else:
                    logger.warning(f"Skipping ContentItem with empty content: id={item.content_id}")
            else:
                logger.warning(f"Skipping invalid content type: {type(item)}")
        return validated

    @staticmethod
    def select_baseline_content_id(contents: List[ContentItem]) -> Optional[int]:
        """
        분석 콘텐츠 목록에서 baseline_content_id 선정

        선정 기준:
        1. updated_at 또는 created_at 중 가장 최신 날짜의 content_id
        2. 시간 정보가 없으면 가장 큰 content_id
        """
        if not contents:
            return None

        # 시간 정보가 있는 콘텐츠 필터링
        contents_with_time = [
            c for c in contents
            if c.updated_at is not None or c.created_at is not None
        ]

        if contents_with_time:
            # 시간 기준 정렬 (updated_at 우선, 없으면 created_at)
            def get_latest_time(c: ContentItem) -> datetime:
                return c.updated_at or c.created_at

            latest = max(contents_with_time, key=get_latest_time)
            return latest.content_id
        else:
            # 시간 정보 없으면 가장 큰 content_id
            return max(c.content_id for c in contents)