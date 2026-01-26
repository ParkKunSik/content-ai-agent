from src.utils.prompt_renderer import PromptRenderer
from src.utils.prompt_template import PromptTemplate
from src.utils.prompt_form_template import PromptFormTemplate

class PromptManager:
    """
    High-level manager for constructing prompts.
    Implemented as a Singleton to share the internal PromptRenderer instance.
    """
    _instance = None
    
    # Summary character limits for detailed analysis refinement
    MAX_MAIN_SUMMARY_CHARS = 300
    MAX_CATEGORY_SUMMARY_CHARS = 50

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

    def get_contents_analysis_prompt(self, project_id: str, combined_summary: str) -> str:
        """
        Constructs the prompt for comprehensive contents analysis.
        Injects the JSON schema automatically.
        """
        template = PromptTemplate.CONTENTS_ANALYSIS.get_template(self._renderer)
        schema = PromptFormTemplate.CONTENTS_ANALYSIS_RESULT.get_render(self._renderer)
        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            response_schema=schema,
            combined_summary=combined_summary
        )

    def get_detailed_analysis_prompt(self, project_id: int, content_items: str) -> str:
        """
        상세 분석 프롬프트 생성 (구조화 및 추출).
        JSON 스키마를 자동으로 주입합니다.
        """
        template = PromptTemplate.DETAILED_ANALYSIS.get_template(self._renderer)
        schema = PromptFormTemplate.DETAILED_ANALYSIS_RESULT.get_render(self._renderer)
        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            response_schema=schema,
            content_items=content_items
        )

    def get_detailed_analysis_summary_refine_prompt(self, project_id: int, raw_analysis_data: str) -> str:
        """
        상세 분석 요약 정제 프롬프트 생성 (요약 최적화).
        JSON 스키마를 자동으로 주입합니다.
        """
        template = PromptTemplate.DETAILED_ANALYSIS_SUMMARY_REFINE.get_template(self._renderer)
        schema = PromptFormTemplate.DETAILED_ANALYSIS_SUMMARY_REFINE_RESULT.get_render(self._renderer)
        return self._renderer.render_with_template(
            template,
            project_id=project_id,
            response_schema=schema,
            raw_analysis_data=raw_analysis_data,
            max_main_summary_chars=self.MAX_MAIN_SUMMARY_CHARS,
            max_category_summary_chars=self.MAX_CATEGORY_SUMMARY_CHARS
        )