import json
from typing import List, Optional

from src.core.config.settings import settings
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.prompt.analysis_content_item import AnalysisContentItem
from src.schemas.models.prompt.multi_project_batch_item import MultiProjectBatchItem
from src.schemas.models.prompt.multi_project_summary_item import MultiProjectSummaryItem
from src.schemas.models.prompt.response.multi_project_analysis_result import MultiProjectAnalysisResult
from src.schemas.models.prompt.response.multi_project_refined_result import MultiProjectRefinedResult
from src.schemas.models.prompt.response.structured_analysis_refined_summary import StructuredAnalysisRefinedSummary
from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult
from src.schemas.models.prompt.structured_analysis_summary import StructuredAnalysisSummary
from src.utils.prompt_renderer import PromptRenderer
from src.utils.prompt_template import PromptTemplate
from src.utils.schema_description_extractor import extract_schema_description


class PromptManager:
    """
    High-level manager for constructing prompts.
    Implemented as a Singleton to share the internal PromptRenderer instance.
    """
    _instance = None

    # Summary character limits for detailed analysis refinement
    @property
    def MAX_MAIN_SUMMARY_CHARS(self) -> int:
        return settings.analysis.MAX_MAIN_SUMMARY_CHARS

    @property
    def MAX_CATEGORY_SUMMARY_CHARS(self) -> int:
        return settings.analysis.MAX_CATEGORY_SUMMARY_CHARS

    @property
    def MAX_INSIGHT_ITEM_CHARS_ANALYSIS(self) -> int:
        return settings.analysis.MAX_INSIGHT_ITEM_CHARS_ANALYSIS

    @property
    def MAX_INSIGHT_ITEM_CHARS_REFINE(self) -> int:
        return settings.analysis.MAX_INSIGHT_ITEM_CHARS_REFINE

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PromptManager, cls).__new__(cls)
            # Initialize renderer only once
            cls._instance._renderer = PromptRenderer()
        return cls._instance

    @property
    def renderer(self) -> PromptRenderer:
        """Access the underlying PromptRenderer instance."""
        return self._renderer

    def get_content_analysis_structuring_prompt(
        self,
        project_id: int,
        project_type: ProjectType,
        content_type: str,
        analysis_content_items: List[AnalysisContentItem],
        previous_result: Optional[StructuredAnalysisResult] = None
    ) -> str:
        """
        상세 분석 프롬프트 생성 (구조화 및 추출).

        Args:
            project_id: 프로젝트 ID
            project_type: 프로젝트 타입
            content_type: 콘텐츠 타입 (문자열)
            analysis_content_items: 분석 대상 콘텐츠 아이템 리스트
            previous_result: 기존 분석 결과 (순차 청킹 시 통합용)
        """
        template = PromptTemplate.CONTENT_ANALYSIS_STRUCTURING.get_template(self._renderer)
        content_items_json = json.dumps(
            [item.model_dump(exclude_none=True) for item in analysis_content_items],
            ensure_ascii=False,
            separators=(',', ':')
        )

        # Schema description 추출 (OpenAI 템플릿에서만 사용, Vertex AI는 무시)
        input_schema_description = extract_schema_description(AnalysisContentItem)
        output_schema_description = extract_schema_description(StructuredAnalysisResult)

        # 기존 결과를 JSON으로 변환 (keywords 제외 - Step2에서 재생성)
        previous_result_json = None
        if previous_result:
            previous_result_json = previous_result.model_dump_json(
                exclude={"keywords"},
                exclude_none=True
            )

        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            project_type=project_type,
            content_type=content_type,
            content_items=content_items_json,
            max_insight_item_chars=self.MAX_INSIGHT_ITEM_CHARS_ANALYSIS,
            input_schema_description=input_schema_description,
            output_schema_description=output_schema_description,
            previous_result=previous_result,
            previous_result_json=previous_result_json
        )

    def get_content_analysis_summary_refine_prompt(
        self,
        project_id: int,
        project_type: ProjectType,
        content_type: str,
        refine_content_items: StructuredAnalysisSummary
    ) -> str:
        """
        상세 분석 요약 정제 프롬프트 생성 (요약 최적화).

        Args:
            project_id: 프로젝트 ID
            project_type: 프로젝트 타입
            content_type: 콘텐츠 타입 (문자열)
            refine_content_items: 정제 대상 분석 요약 데이터
        """
        template = PromptTemplate.CONTENT_ANALYSIS_SUMMARY_REFINE.get_template(self._renderer)
        raw_analysis_data = refine_content_items.model_dump_json(exclude_none=True)

        # Schema description 추출 (OpenAI 템플릿에서만 사용, Vertex AI는 무시)
        output_schema_description = extract_schema_description(StructuredAnalysisRefinedSummary)

        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            project_type=project_type,
            content_type=content_type,
            raw_analysis_data=raw_analysis_data,
            max_main_summary_chars=self.MAX_MAIN_SUMMARY_CHARS,
            max_category_summary_chars=self.MAX_CATEGORY_SUMMARY_CHARS,
            max_insight_item_chars=self.MAX_INSIGHT_ITEM_CHARS_REFINE,
            output_schema_description=output_schema_description
        )

    # ========== Multi-Project 배치 분석 ==========

    def get_multi_project_analysis_structuring_prompt(
        self,
        projects: List[MultiProjectBatchItem]
    ) -> str:
        """
        Multi-Project 배치 분석 프롬프트 생성 (Step 1: 구조화 및 추출).

        Args:
            projects: 분석 대상 프로젝트 리스트
        """
        template = PromptTemplate.MULTI_PROJECT_CONTENT_ANALYSIS_STRUCTURING.get_template(self._renderer)

        # 프로젝트 데이터를 JSON으로 변환
        projects_data = []
        for project in projects:
            project_dict = project.model_dump(exclude_none=True)
            # previous_result가 있으면 keywords 제외
            if project.previous_result:
                project_dict['previous_result'] = project.previous_result.model_dump(
                    exclude={"keywords"},
                    exclude_none=True
                )
            projects_data.append(project_dict)

        projects_json = json.dumps(
            {"projects": projects_data},
            ensure_ascii=False,
            separators=(',', ':')
        )

        # Schema description 추출 (Multi-Project는 중첩이 깊어 max_depth 증가 필요)
        input_schema_description = extract_schema_description(MultiProjectBatchItem, max_depth=8)
        output_schema_description = extract_schema_description(MultiProjectAnalysisResult, max_depth=8)

        return self._renderer.render_with_template(
            template,
            projects_json=projects_json,
            max_insight_item_chars=self.MAX_INSIGHT_ITEM_CHARS_ANALYSIS,
            input_schema_description=input_schema_description,
            output_schema_description=output_schema_description
        )

    def get_multi_project_analysis_refine_prompt(
        self,
        projects: List[MultiProjectSummaryItem]
    ) -> str:
        """
        Multi-Project 배치 요약 정제 프롬프트 생성 (Step 2: 요약 최적화).

        Args:
            projects: 정제 대상 프로젝트 리스트
        """
        template = PromptTemplate.MULTI_PROJECT_CONTENT_ANALYSIS_SUMMARY_REFINE.get_template(self._renderer)

        # 프로젝트 데이터를 JSON으로 변환
        projects_data = [p.model_dump(exclude_none=True) for p in projects]
        projects_json = json.dumps(
            {"projects": projects_data},
            ensure_ascii=False,
            separators=(',', ':')
        )

        # Schema description 추출 (Multi-Project는 중첩이 깊어 max_depth 증가 필요)
        input_schema_description = extract_schema_description(MultiProjectSummaryItem, max_depth=8)
        output_schema_description = extract_schema_description(MultiProjectRefinedResult, max_depth=8)

        return self._renderer.render_with_template(
            template,
            projects_json=projects_json,
            max_main_summary_chars=self.MAX_MAIN_SUMMARY_CHARS,
            max_category_summary_chars=self.MAX_CATEGORY_SUMMARY_CHARS,
            max_insight_item_chars=self.MAX_INSIGHT_ITEM_CHARS_REFINE,
            input_schema_description=input_schema_description,
            output_schema_description=output_schema_description
        )
