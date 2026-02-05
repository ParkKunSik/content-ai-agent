import logging
from typing import List, Union

from src.core.config import settings
from src.core.elasticsearch_config import es_manager, ElasticsearchConfig
from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.prompt.structured_analysis_response import StructuredAnalysisResponse
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

    async def analysis(
        self, 
        project_id: int,
        project_type: ProjectType,
        contents: List[Union[str, ContentItem]],
        analysis_mode: AnalysisMode
    ) -> StructuredAnalysisResponse:
        """
        Performs a detailed 2-step analysis:
        Step 1: Structure & Extract (Main Analysis)
        Step 2: Refine & Summarize (Optimization)
        Returns base analysis data updated with refined summaries from refinement step.
        """
        logger.info(f"Starting detailed analysis for Project: {project_id}, Mode: {analysis_mode}")
        
        # 1. Preprocess contents
        content_items = self._preprocess_contents(contents)
        
        # 2. Step 1: Main Analysis (PRO_DATA_ANALYST)
        logger.info("Executing Step 1: Main Analysis")
        base_analysis = await self.llm_service.structure_content_analysis(
            project_id=project_id,
            project_type=project_type,
            content_items=[item.model_dump() for item in content_items]
        )
        logger.info(f"Step 1 completed. Categories found: {len(base_analysis.categories)}")
        
        # 3. Step 2: Refine Summary
        # Uses the persona defined in AnalysisMode for refinement
        logger.info(f"Executing Step 2: Refinement with persona {analysis_mode.persona_type}")
        refinement_result = await self.llm_service.refine_analysis_summary(
            project_id=project_id,
            project_type=project_type,
            raw_analysis_data=base_analysis.model_dump_json(),
            persona_type=analysis_mode.persona_type
        )
        
        # 4. Merge Refined Summaries into Base Analysis
        base_analysis.summary = refinement_result.summary
        
        # Create a lookup map for refined category summaries
        refined_map = {cat.category_key: cat.summary for cat in refinement_result.categories}
        
        for category in base_analysis.categories:
            if category.category_key in refined_map:
                category.summary = refined_map[category.category_key]
        
        logger.info("Detailed analysis completed successfully")
        
        return base_analysis

    async def funding_preorder_project_analysis(
            self,
            project_id: int,
            content_type: ExternalContentType,
            analysis_mode: AnalysisMode
    ) -> StructuredAnalysisResponse:
        return await self.project_analysis(project_id, ProjectType.FUNDING_AND_PREORDER, content_type, analysis_mode)

    async def project_analysis(
        self,
        project_id: int,
        project_type: ProjectType,
        content_type: ExternalContentType,
        analysis_mode: AnalysisMode
    ) -> StructuredAnalysisResponse:
        """
        Performs project-based analysis by retrieving content from Elasticsearch.
        
        Args:
            project_id: 프로젝트 ID
            project_type: 프로젝트 타입
            content_type: 외부 콘텐츠 타입 (ExternalContentType)
            analysis_mode: 분석 모드
            
        Returns:
            StructuredAnalysisResponse: 분석 결과
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
            # TODO: 빈 결과에 대한 처리 로직 추가 필요
            raise ValueError(f"프로젝트 {project_id}의 {content_type} 콘텐츠를 찾을 수 없습니다.")
        
        logger.info(f"Retrieved {len(content_items)} content items from ES")
        
        # 2. 기존 analysis 메서드 활용
        analysis_result = await self.analysis(
            project_id=project_id,
            project_type=project_type,
            contents=content_items,
            analysis_mode=analysis_mode
        )
        
        # 3. 저장 로직은 추후 구현 예정 (현재는 분석만 수행)
        # TODO: ESContentAnalysisResultService를 통한 결과 저장 구현
        # await self.save_analysis_result(...)
        
        logger.info(f"Project analysis completed for project {project_id}")
        
        return analysis_result

    def _preprocess_contents(self, contents: List[Union[str, ContentItem]]) -> List[ContentItem]:
        """Converts raw strings to ContentItem objects if necessary."""
        processed = []
        for idx, item in enumerate(contents):
            if isinstance(item, str):
                # Generate a temporary ID for string inputs
                processed.append(ContentItem(content_id=idx + 1, content=item))
            elif isinstance(item, ContentItem):
                processed.append(item)
            else:
                logger.warning(f"Skipping invalid content type: {type(item)}")
        return processed