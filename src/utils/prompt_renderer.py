import os
import re

from jinja2 import Environment, FileSystemLoader, Template


class PromptRenderer:
    """
    Low-level class to handle Jinja2 template rendering.
    """
    def __init__(self, template_dir: str = None):
        if template_dir is None:
            # Assume templates are in src/prompts/templates/
            current_dir = os.path.dirname(os.path.abspath(__file__))
            template_dir = os.path.join(current_dir, "..", "prompts", "templates")
        
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def get_template(self, template_name: str) -> Template:
        """template_name을 전달하면 Template class를 반환하는 메서드."""
        return self.env.get_template(template_name)

    def render(self, template_name: str, **kwargs) -> str:
        """Renders a Jinja2 template with context."""
        return self.render_with_template(self.get_template(template_name), **kwargs)

    def render_with_template(self, template: Template, **kwargs) -> str:
        """Template class를 직접 받아서 렌더링."""
        return template.render(**kwargs).strip()

    def get_minified_schema(self, template_name: str) -> str:
        """Loads and minifies a schema template."""
        return self.get_minified_schema_with_template(self.get_template(template_name))

    def get_minified_schema_with_template(self, template: Template) -> str:
        """Template class를 직접 받아서 미니파이된 스키마 반환."""
        rendered = template.render()
        return re.sub(r'\s+', ' ', rendered).strip()
