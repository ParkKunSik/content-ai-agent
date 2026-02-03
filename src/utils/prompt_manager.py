from src.core.config import settings
from src.schemas.enums.project_type import ProjectType
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

    def get_detailed_analysis_prompt(self, project_id: int, project_type: ProjectType, content_items: str) -> str:
        """
        상세 분석 프롬프트 생성 (구조화 및 추출).
        """
        template = PromptTemplate.DETAILED_ANALYSIS.get_template(self._renderer)
        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            project_type=project_type,
            content_items=content_items
        )

    def get_detailed_analysis_summary_refine_prompt(self, project_id: int, project_type: ProjectType, raw_analysis_data: str) -> str:
        """
        상세 분석 요약 정제 프롬프트 생성 (요약 최적화).
        """
        template = PromptTemplate.DETAILED_ANALYSIS_SUMMARY_REFINE.get_template(self._renderer)
        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            project_type=project_type,
            raw_analysis_data=raw_analysis_data,
            max_main_summary_chars=self.MAX_MAIN_SUMMARY_CHARS,
            max_category_summary_chars=self.MAX_CATEGORY_SUMMARY_CHARS
        )