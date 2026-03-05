import asyncio
import concurrent.futures
import logging
import time
from typing import List, Optional, Tuple, Type

from pydantic import BaseModel

from src.core.config.settings import settings
from src.core.llm.enums import FinishReason, ProviderType, ResponseFormat
from src.core.llm.models import LLMResponse, PersonaConfig
from src.core.llm.registry import ProviderRegistry
from src.core.validation_error_handler import ValidationErrorHandler
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.mime_type import MimeType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.common.llm_usage_info import LLMUsageInfo
from src.schemas.models.prompt.analysis_content_item import AnalysisContentItem
from src.schemas.models.prompt.multi_project_batch_item import MultiProjectBatchItem
from src.schemas.models.prompt.multi_project_summary_item import MultiProjectSummaryItem
from src.schemas.models.prompt.response.multi_project_analysis_result import (
    MultiProjectAnalysisResult,
    MultiProjectAnalysisResultItem,
)
from src.schemas.models.prompt.response.multi_project_refined_result import (
    MultiProjectRefinedResult,
    MultiProjectRefinedResultItem,
)
from src.schemas.models.prompt.response.structured_analysis_refined_summary import StructuredAnalysisRefinedSummary
from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult
from src.schemas.models.prompt.structured_analysis_summary import StructuredAnalysisSummary
from src.utils.prompt_manager import PromptManager
from src.utils.token_cost_calculator import create_llm_usage_info

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM 통신을 전담하는 서비스 클래스.
    Provider 중립적으로 설계되어 Vertex AI, OpenAI 등을 지원한다.
    """

    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager
        self.validation_handler = ValidationErrorHandler(max_retries=3, delay_between_retries=1.0)
        self._ensure_provider_initialized()

    def _ensure_provider_initialized(self) -> None:
        """현재 설정된 LLM Provider가 초기화되었는지 확인하고 필요시 초기화한다."""
        provider_type = self._get_provider_type()
        if not ProviderRegistry.is_initialized(provider_type):
            ProviderRegistry.initialize(provider_type)

    def _get_provider_type(self) -> ProviderType:
        """현재 설정된 LLM Provider 타입을 반환한다."""
        return settings.llm_provider

    async def count_total_tokens(self, contents: List[str]) -> int:
        total = 0
        model_name = PersonaType.COMMON_TOKEN_COUNTER.get_model_name()
        for text in contents:
            try:
                token_count = ProviderRegistry.count_tokens(text, model_name)
                total += token_count
            except Exception as e:
                logger.warning(f"Failed to count tokens: {e}")
                total += len(text) // 2
        return total

    async def generate(
        self,
        prompt: str,
        persona_type: PersonaType,
        mime_type: MimeType = MimeType.TEXT_PLAIN,
        response_schema: Optional[Type[BaseModel]] = None
    ) -> str:
        """Generic method to generate content using a specific persona."""
        llm_response = self._generate_raw(prompt, persona_type, mime_type, response_schema)
        return self._extract_text_safely(llm_response, persona_type)

    def _generate_raw(
        self,
        prompt: str,
        persona_type: PersonaType,
        mime_type: MimeType = MimeType.TEXT_PLAIN,
        response_schema: Optional[Type[BaseModel]] = None
    ) -> LLMResponse:
        """LLM 호출 후 LLMResponse 전체를 반환하는 내부 메서드."""
        # PersonaConfig 생성
        response_format = ResponseFormat.JSON if mime_type == MimeType.APPLICATION_JSON else ResponseFormat.TEXT
        persona_config = PersonaConfig(
            name=persona_type.name,
            model_name=persona_type.get_model_name(),
            temperature=persona_type.temperature,
            system_instruction=persona_type.get_instruction(self.prompt_manager.renderer),
            response_format=response_format,
            response_schema=response_schema,
        )

        # ProviderRegistry를 통한 세션 생성
        session = ProviderRegistry.start_session(persona_config)

        # LLM 콘텐츠 생성 및 반환
        return session.generate_content(prompt)

    def _generate_raw_with_text(
        self,
        prompt: str,
        persona_type: PersonaType,
        mime_type: MimeType = MimeType.TEXT_PLAIN,
        response_schema: Optional[Type[BaseModel]] = None
    ) -> Tuple[str, LLMResponse]:
        """LLM 호출 후 (텍스트, LLMResponse) 튜플을 반환하는 내부 메서드."""
        llm_response = self._generate_raw(prompt, persona_type, mime_type, response_schema)
        text = self._extract_text_safely(llm_response, persona_type)
        return text, llm_response

    async def generate_with_usage(
        self,
        prompt: str,
        persona_type: PersonaType,
        step: int,
        mime_type: MimeType = MimeType.TEXT_PLAIN,
        response_schema: Optional[Type[BaseModel]] = None
    ) -> Tuple[str, LLMUsageInfo]:
        """LLM 생성 + 사용 정보(토큰, 소요시간) 반환."""
        start_time = time.time()

        llm_response = self._generate_raw(prompt, persona_type, mime_type, response_schema)
        text = self._extract_text_safely(llm_response, persona_type)

        duration_ms = int((time.time() - start_time) * 1000)

        usage_info = create_llm_usage_info(
            step=step,
            model=persona_type.get_model_name(),
            input_tokens=llm_response.usage.prompt_tokens,
            output_tokens=llm_response.usage.completion_tokens,
            thinking_tokens=llm_response.usage.thinking_tokens,
            duration_ms=duration_ms
        )

        return text, usage_info

    def _extract_text_safely(self, response: LLMResponse, persona_type: PersonaType) -> str:
        """LLMResponse에서 안전하게 텍스트를 추출한다 (Provider 중립)."""
        # 종료 사유에 따른 분기 처리
        if response.finish_reason == FinishReason.SAFETY:
            raise ValueError(f"안전 정책에 의해 응답이 거부되었습니다 (persona: {persona_type.value})")
        elif response.finish_reason == FinishReason.CONTENT_FILTER:
            raise ValueError(f"콘텐츠 필터에 의해 응답이 거부되었습니다 (persona: {persona_type.value})")
        elif response.finish_reason == FinishReason.RECITATION:
            raise ValueError(f"인용 감지로 인해 응답이 거부되었습니다 (persona: {persona_type.value})")
        elif response.finish_reason == FinishReason.MAX_TOKENS:
            logger.warning(f"답변이 너무 길어 중간에 끊겼습니다 (persona: {persona_type.value})")
            # MAX_TOKENS의 경우 부분 응답이라도 사용

        # 텍스트가 비어있는 경우 처리
        if not response.text:
            raise ValueError(f"모델이 응답을 생성하지 못했습니다 (persona: {persona_type.value})")

        return response.text

    def _convert_to_analysis_items(self, content_items: List[ContentItem]) -> List[AnalysisContentItem]:
        """
        ContentItem 리스트를 AnalysisContentItem 리스트로 변환
        
        Args:
            content_items: ContentItem 객체 리스트
            
        Returns:
            List[AnalysisContentItem]: 분석용 AnalysisContentItem 리스트
        """
        analysis_items = []
        for content_item in content_items:
            # 토큰 절약을 위해 has_image가 True인 경우만 설정, 나머지는 None 처리
            analysis_item = AnalysisContentItem(
                id=content_item.content_id,  # int 타입 유지
                content=content_item.content,
                has_image=content_item.has_image if content_item.has_image is True else None
            )
            analysis_items.append(analysis_item)
        return analysis_items

    async def structure_content_analysis(
        self,
        project_id: int,
        project_type: ProjectType,
        content_items: List[ContentItem],
        content_type: Optional[ExternalContentType] = None,
        previous_result: Optional[StructuredAnalysisResult] = None
    ) -> Tuple[StructuredAnalysisResult, LLMUsageInfo]:
        """
        상세 분석 수행 (Main Analysis) - Phase 2 세션 기반 검증 적용
        PRO_DATA_ANALYST 페르소나를 사용하여 콘텐츠를 구조화하고 심층 분석합니다.

        Args:
            project_id: 프로젝트 ID
            project_type: 프로젝트 타입
            content_items: 분석 대상 콘텐츠 (새 콘텐츠)
            content_type: 콘텐츠 타입
            previous_result: 기존 분석 결과 (순차 청킹 시 통합용)
                            있으면 기존 + 새 콘텐츠를 통합한 결과 출력

        Returns:
            Tuple[StructuredAnalysisResult, LLMUsageInfo]: 분석 결과와 LLM 사용 정보
        """
        analysis_items = self._convert_to_analysis_items(content_items)

        prompt = self.prompt_manager.get_content_analysis_structuring_prompt(
            project_id=project_id,
            project_type=project_type,
            content_type=content_type.value if content_type else "ALL",
            analysis_content_items=analysis_items,
            previous_result=previous_result
        )

        persona_type = PersonaType.PRO_DATA_ANALYST
        start_time = time.time()

        # ValidationErrorHandler를 사용한 재시도 로직 적용 (토큰 정보 포함)
        async def response_generator():
            return self._generate_raw_with_text(
                prompt, persona_type,
                mime_type=MimeType.APPLICATION_JSON,
                response_schema=StructuredAnalysisResult
            )

        result, llm_response = await self.validation_handler.validate_with_retry_and_usage(
            response_generator=response_generator,
            model_class=StructuredAnalysisResult,
            error_context="content_analysis_structuring"
        )

        duration_ms = int((time.time() - start_time) * 1000)

        usage_info = create_llm_usage_info(
            step=1,
            model=persona_type.get_model_name(),
            input_tokens=llm_response.usage.prompt_tokens,
            output_tokens=llm_response.usage.completion_tokens,
            thinking_tokens=llm_response.usage.thinking_tokens,
            duration_ms=duration_ms
        )

        return result, usage_info

    async def refine_analysis_summary(
        self,
        project_id: int,
        project_type: ProjectType,
        refine_content_items: StructuredAnalysisSummary,
        persona_type: PersonaType,
        content_type: Optional[ExternalContentType] = None
    ) -> Tuple[StructuredAnalysisRefinedSummary, LLMUsageInfo]:
        """
        분석 요약 정제 (Refinement) - Phase 2 세션 기반 검증 적용
        분석된 데이터를 바탕으로 요약의 길이를 최적화하고 정제합니다.

        Returns:
            Tuple[StructuredAnalysisRefinedSummary, LLMUsageInfo]: 정제된 결과와 LLM 사용 정보
        """
        prompt = self.prompt_manager.get_content_analysis_summary_refine_prompt(
            project_id=project_id,
            project_type=project_type,
            content_type=content_type.value if content_type else "ALL",
            refine_content_items=refine_content_items
        )

        start_time = time.time()

        # ValidationErrorHandler를 사용한 재시도 로직 적용 (토큰 정보 포함)
        async def response_generator():
            return self._generate_raw_with_text(
                prompt, persona_type,
                mime_type=MimeType.APPLICATION_JSON,
                response_schema=StructuredAnalysisRefinedSummary
            )

        result, llm_response = await self.validation_handler.validate_with_retry_and_usage(
            response_generator=response_generator,
            model_class=StructuredAnalysisRefinedSummary,
            error_context="analysis_refinement"
        )

        duration_ms = int((time.time() - start_time) * 1000)

        usage_info = create_llm_usage_info(
            step=2,
            model=persona_type.get_model_name(),
            input_tokens=llm_response.usage.prompt_tokens,
            output_tokens=llm_response.usage.completion_tokens,
            thinking_tokens=llm_response.usage.thinking_tokens,
            duration_ms=duration_ms
        )

        return result, usage_info

    async def multi_project_structure_analysis(
        self,
        projects: List[MultiProjectBatchItem]
    ) -> Tuple[MultiProjectAnalysisResult, LLMUsageInfo]:
        """
        Multi-Project 배치 구조화 분석 (Step 1)

        여러 프로젝트를 하나의 LLM 호출로 처리하여 토큰 효율성을 극대화합니다.

        Args:
            projects: 분석 대상 프로젝트 배열 (각 프로젝트별 content_items, previous_result 포함)

        Returns:
            Tuple[MultiProjectAnalysisResult, LLMUsageInfo]: 분석 결과와 LLM 사용 정보
        """
        prompt = self.prompt_manager.get_multi_project_analysis_structuring_prompt(projects)

        persona_type = PersonaType.PRO_DATA_ANALYST
        start_time = time.time()

        async def response_generator():
            return self._generate_raw_with_text(
                prompt, persona_type,
                mime_type=MimeType.APPLICATION_JSON,
                response_schema=MultiProjectAnalysisResult
            )

        result, llm_response = await self.validation_handler.validate_with_retry_and_usage(
            response_generator=response_generator,
            model_class=MultiProjectAnalysisResult,
            error_context="multi_project_structure_analysis"
        )

        duration_ms = int((time.time() - start_time) * 1000)

        usage_info = create_llm_usage_info(
            step=1,
            model=persona_type.get_model_name(),
            input_tokens=llm_response.usage.prompt_tokens,
            output_tokens=llm_response.usage.completion_tokens,
            thinking_tokens=llm_response.usage.thinking_tokens,
            duration_ms=duration_ms
        )

        logger.info(
            f"Multi-project Step 1 completed: {len(projects)} projects, "
            f"{usage_info.input_tokens}/{usage_info.output_tokens} tokens"
        )

        return result, usage_info

    async def multi_project_refine_analysis(
        self,
        projects: List[MultiProjectSummaryItem],
        persona_type: PersonaType
    ) -> Tuple[MultiProjectRefinedResult, LLMUsageInfo]:
        """
        Multi-Project 배치 요약 정제 (Step 2)

        여러 프로젝트의 분석 결과를 하나의 LLM 호출로 정제합니다.

        Args:
            projects: 정제 대상 프로젝트 리스트 (Step 1 결과 기반)
            persona_type: 정제 페르소나 (예: CUSTOMER_FACING_SMART_BOT)

        Returns:
            Tuple[MultiProjectRefinedResult, LLMUsageInfo]: 정제된 결과와 LLM 사용 정보
        """
        prompt = self.prompt_manager.get_multi_project_analysis_refine_prompt(projects)

        start_time = time.time()

        async def response_generator():
            return self._generate_raw_with_text(
                prompt, persona_type,
                mime_type=MimeType.APPLICATION_JSON,
                response_schema=MultiProjectRefinedResult
            )

        result, llm_response = await self.validation_handler.validate_with_retry_and_usage(
            response_generator=response_generator,
            model_class=MultiProjectRefinedResult,
            error_context="multi_project_refine_analysis"
        )

        duration_ms = int((time.time() - start_time) * 1000)

        usage_info = create_llm_usage_info(
            step=2,
            model=persona_type.get_model_name(),
            input_tokens=llm_response.usage.prompt_tokens,
            output_tokens=llm_response.usage.completion_tokens,
            thinking_tokens=llm_response.usage.thinking_tokens,
            duration_ms=duration_ms
        )

        logger.info(
            f"Multi-project Step 2 completed: {len(projects)} projects, "
            f"{usage_info.input_tokens}/{usage_info.output_tokens} tokens"
        )

        return result, usage_info

    # =========================================================================
    # Parallel Project Analysis (개별 프로젝트 병렬 처리)
    # =========================================================================

    async def parallel_project_structure_analysis(
        self,
        projects: List[MultiProjectBatchItem],
        max_workers: int = 10
    ) -> Tuple[MultiProjectAnalysisResult, List[LLMUsageInfo]]:
        """
        개별 프로젝트 병렬 구조화 분석 (Step 1)

        각 프로젝트를 독립적인 LLM 호출로 처리하여 Cross-Contamination 위험을 제거합니다.
        ThreadPoolExecutor를 사용하여 진정한 병렬 처리를 수행합니다.

        Args:
            projects: 분석 대상 프로젝트 배열
            max_workers: 최대 동시 실행 수 (기본값: 10)

        Returns:
            Tuple[MultiProjectAnalysisResult, List[LLMUsageInfo]]:
                - 통합된 분석 결과 (Multi-Project 형식과 호환)
                - 각 프로젝트별 LLM 사용 정보 리스트
        """
        start_time = time.time()

        def process_single_project(item: MultiProjectBatchItem) -> Tuple[MultiProjectAnalysisResultItem, LLMUsageInfo]:
            """단일 프로젝트를 동기적으로 처리 (ThreadPoolExecutor용)"""
            return asyncio.run(self._process_single_structure_analysis(item))

        results: List[MultiProjectAnalysisResultItem] = []
        usages: List[LLMUsageInfo] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(process_single_project, item): item
                for item in projects
            }

            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result_item, usage_info = future.result()
                    results.append(result_item)
                    usages.append(usage_info)
                except Exception as e:
                    logger.error(f"Project {item.project} failed: {e}")
                    raise

        total_duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Parallel Step 1 completed: {len(projects)} projects in {total_duration_ms}ms, "
            f"workers={max_workers}"
        )

        return MultiProjectAnalysisResult(results=results), usages

    async def _process_single_structure_analysis(
        self,
        item: MultiProjectBatchItem
    ) -> Tuple[MultiProjectAnalysisResultItem, LLMUsageInfo]:
        """단일 프로젝트 구조화 분석 (내부 메서드)"""
        # 문자열 → enum 변환
        project_type_enum = ProjectType(item.project_type)

        # content_items는 이미 AnalysisContentItem 리스트
        prompt = self.prompt_manager.get_content_analysis_structuring_prompt(
            project_id=item.project,
            project_type=project_type_enum,
            content_type=item.content_type if item.content_type else "ALL",
            analysis_content_items=item.content_items,
            previous_result=item.previous_result
        )

        persona_type = PersonaType.PRO_DATA_ANALYST
        start_time = time.time()

        async def response_generator():
            return self._generate_raw_with_text(
                prompt, persona_type,
                mime_type=MimeType.APPLICATION_JSON,
                response_schema=StructuredAnalysisResult
            )

        result, llm_response = await self.validation_handler.validate_with_retry_and_usage(
            response_generator=response_generator,
            model_class=StructuredAnalysisResult,
            error_context=f"parallel_structure_analysis_project_{item.project}"
        )

        duration_ms = int((time.time() - start_time) * 1000)

        usage_info = create_llm_usage_info(
            step=1,
            model=persona_type.get_model_name(),
            input_tokens=llm_response.usage.prompt_tokens,
            output_tokens=llm_response.usage.completion_tokens,
            thinking_tokens=llm_response.usage.thinking_tokens,
            duration_ms=duration_ms
        )

        result_item = MultiProjectAnalysisResultItem(
            project=item.project,
            project_type=item.project_type,
            content_type=item.content_type,
            result=result
        )

        return result_item, usage_info

    async def parallel_project_refine_analysis(
        self,
        projects: List[MultiProjectSummaryItem],
        persona_type: PersonaType,
        max_workers: int = 10
    ) -> Tuple[MultiProjectRefinedResult, List[LLMUsageInfo]]:
        """
        개별 프로젝트 병렬 요약 정제 (Step 2)

        각 프로젝트를 독립적인 LLM 호출로 정제하여 Cross-Contamination 위험을 제거합니다.

        Args:
            projects: 정제 대상 프로젝트 리스트 (Step 1 결과 기반)
            persona_type: 정제 페르소나 (예: CUSTOMER_FACING_SMART_BOT)
            max_workers: 최대 동시 실행 수 (기본값: 10)

        Returns:
            Tuple[MultiProjectRefinedResult, List[LLMUsageInfo]]:
                - 통합된 정제 결과
                - 각 프로젝트별 LLM 사용 정보 리스트
        """
        start_time = time.time()

        def process_single_project(item: MultiProjectSummaryItem) -> Tuple[MultiProjectRefinedResultItem, LLMUsageInfo]:
            """단일 프로젝트를 동기적으로 처리 (ThreadPoolExecutor용)"""
            return asyncio.run(self._process_single_refine_analysis(item, persona_type))

        results: List[MultiProjectRefinedResultItem] = []
        usages: List[LLMUsageInfo] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(process_single_project, item): item
                for item in projects
            }

            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result_item, usage_info = future.result()
                    results.append(result_item)
                    usages.append(usage_info)
                except Exception as e:
                    logger.error(f"Project {item.project} refinement failed: {e}")
                    raise

        total_duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Parallel Step 2 completed: {len(projects)} projects in {total_duration_ms}ms, "
            f"workers={max_workers}"
        )

        return MultiProjectRefinedResult(results=results), usages

    async def _process_single_refine_analysis(
        self,
        item: MultiProjectSummaryItem,
        persona_type: PersonaType
    ) -> Tuple[MultiProjectRefinedResultItem, LLMUsageInfo]:
        """단일 프로젝트 요약 정제 (내부 메서드)"""
        # 문자열 → enum 변환
        project_type_enum = ProjectType(item.project_type)

        prompt = self.prompt_manager.get_content_analysis_summary_refine_prompt(
            project_id=item.project,
            project_type=project_type_enum,
            content_type=item.content_type if item.content_type else "ALL",
            refine_content_items=item.analysis_data
        )

        start_time = time.time()

        async def response_generator():
            return self._generate_raw_with_text(
                prompt, persona_type,
                mime_type=MimeType.APPLICATION_JSON,
                response_schema=StructuredAnalysisRefinedSummary
            )

        result, llm_response = await self.validation_handler.validate_with_retry_and_usage(
            response_generator=response_generator,
            model_class=StructuredAnalysisRefinedSummary,
            error_context=f"parallel_refine_analysis_project_{item.project}"
        )

        duration_ms = int((time.time() - start_time) * 1000)

        usage_info = create_llm_usage_info(
            step=2,
            model=persona_type.get_model_name(),
            input_tokens=llm_response.usage.prompt_tokens,
            output_tokens=llm_response.usage.completion_tokens,
            thinking_tokens=llm_response.usage.thinking_tokens,
            duration_ms=duration_ms
        )

        result_item = MultiProjectRefinedResultItem(
            project=item.project,
            project_type=item.project_type,
            content_type=item.content_type,
            result=result
        )

        return result_item, usage_info

