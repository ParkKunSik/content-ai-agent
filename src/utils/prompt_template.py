from enum import Enum
from typing import Dict

from jinja2 import Template

from src.core.config import settings
from src.utils.prompt_renderer import PromptRenderer


class PromptTemplate(Enum):
    """
    프롬프트 템플릿과 스키마 정의 및 캐시 관리를 위한 내부 Enum.
    각 템플릿은 (template_name)으로 정의되며, provider별로 다른 경로에서 로드됩니다.
    """

    # 상세 분석 2단계 템플릿
    CONTENT_ANALYSIS_STRUCTURING = ("content_analysis_structuring.jinja2")
    CONTENT_ANALYSIS_SUMMARY_REFINE = ("content_analysis_summary_refine.jinja2")

    def __init__(self, template_name: str):
        self.template_name = template_name
        self._cached_templates: Dict[str, Template] = {}

    def get_template(self, renderer: PromptRenderer) -> Template:
        """
        Provider별 Template을 캐시에서 가져오거나 처음 호출 시 로드하여 캐시에 저장.

        Args:
            renderer: PromptRenderer 인스턴스
        """
        provider = settings.LLM_PROVIDER  # ProviderType enum

        # Provider별 캐시 확인
        if provider not in self._cached_templates:
            provider_path = provider.value.lower()  # VERTEX_AI → vertex_ai, OPENAI → openai
            template_path = f"task/{provider_path}/{self.template_name}"
            self._cached_templates[provider] = renderer.get_template(template_path)

        return self._cached_templates[provider]