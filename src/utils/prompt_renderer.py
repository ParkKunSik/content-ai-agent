import os
import re
from jinja2 import Environment, FileSystemLoader

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

    def render(self, template_name: str, **kwargs) -> str:
        """Renders a Jinja2 template with context."""
        template = self.env.get_template(template_name)
        return template.render(**kwargs).strip()

    def get_minified_schema(self, template_name: str) -> str:
        """Loads and minifies a schema template."""
        template = self.env.get_template(template_name)
        rendered = template.render()
        return re.sub(r'\s+', ' ', rendered).strip()
