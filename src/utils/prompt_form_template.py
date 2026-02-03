from enum import Enum
from jinja2 import Template
from src.utils.prompt_renderer import PromptRenderer

class PromptFormTemplate(Enum):
    """
    프롬프트 FORM 템플릿과 스키마 정의 및 캐시 관리를 위한 내부 Enum.
    각 템플릿은 (template_path)로 정의됩니다.
    """

    def __init__(self, template_path: str):
        self.template_path = template_path
        self._cached_template = None
        self._cached_render = None

    def get_template(self, renderer: PromptRenderer) -> Template:
        """Template class를 캐시에서 가져오거나 처음 호출 시 로드하여 캐시에 저장."""
        if self._cached_template is None:
            self._cached_template = renderer.get_template(self.template_path)
        return self._cached_template

    def get_render(self, renderer: PromptRenderer) -> str:
        """렌더 데이터를 캐시에서 가져오거나 처음 호출 시 렌더링하여 캐시에 저장."""
        if self._cached_render is None:
            schema_template = self.get_template(renderer)
            self._cached_render = renderer.get_minified_schema_with_template(schema_template)
        return self._cached_render