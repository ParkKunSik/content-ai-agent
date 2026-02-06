import json
from typing import List

from src.core.config import settings
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.prompt.analysis_content_item import AnalysisContentItem
from src.schemas.models.prompt.structured_analysis_summary import StructuredAnalysisSummary
from src.utils.prompt_renderer import PromptRenderer
from src.utils.prompt_template import PromptTemplate


class PromptManager:
    """
    High-level manager for constructing prompts.
    Implemented as a Singleton to share the internal PromptRenderer instance.
    """
    _instance = None

    # Summary character limits for detailed analysis refinement
    @property
    def MAX_MAIN_SUMMARY_CHARS(self) -> int:
        return settings.MAX_MAIN_SUMMARY_CHARS

    @property
    def MAX_CATEGORY_SUMMARY_CHARS(self) -> int:
        return settings.MAX_CATEGORY_SUMMARY_CHARS

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
        analysis_content_items: List[AnalysisContentItem]
    ) -> str:
        """
        상세 분석 프롬프트 생성 (구조화 및 추출).

        Args:
            project_id: 프로젝트 ID
            project_type: 프로젝트 타입
            content_type: 콘텐츠 타입 (문자열)
            analysis_content_items: 분석 대상 콘텐츠 아이템 리스트
        """
        template = PromptTemplate.CONTENT_ANALYSIS_STRUCTURING.get_template(self._renderer)
        content_items_json = json.dumps(
            [item.model_dump(exclude_none=True) for item in analysis_content_items],
            ensure_ascii=False,
            separators=(',', ':')
        )
        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            project_type=project_type,
            content_type=content_type,
            content_items=content_items_json
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
        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            project_type=project_type,
            content_type=content_type,
            raw_analysis_data=raw_analysis_data,
            max_main_summary_chars=self.MAX_MAIN_SUMMARY_CHARS,
            max_category_summary_chars=self.MAX_CATEGORY_SUMMARY_CHARS
        )
