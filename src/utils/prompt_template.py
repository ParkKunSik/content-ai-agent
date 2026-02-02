from enum import Enum
from jinja2 import Template
from src.utils.prompt_renderer import PromptRenderer

class PromptTemplate(Enum):
    """
    프롬프트 템플릿과 스키마 정의 및 캐시 관리를 위한 내부 Enum.
    각 템플릿은 (template_path)로 정의됩니다.
    """

    # 기존 콘텐츠 분석
    CONTENTS_ANALYSIS = ("task/v1/contents_analysis.jinja2")

    # 상세 분석 2단계 템플릿
    DETAILED_ANALYSIS = ("task/v1/detailed_analysis.jinja2")
    DETAILED_ANALYSIS_SUMMARY_REFINE = ("task/v1/detailed_analysis_summary_refine.jinja2")

    def __init__(self, template_path: str):
        self.template_path = template_path
        self._cached_template = None

    def get_template(self, renderer: PromptRenderer) -> Template:
        """Template class를 캐시에서 가져오거나 처음 호출 시 로드하여 캐시에 저장."""
        if self._cached_template is None:
            self._cached_template = renderer.get_template(self.template_path)
        return self._cached_template