from src.utils.prompt_renderer import PromptRenderer

class PromptManager:
    """
    High-level manager for constructing prompts.
    Implemented as a Singleton to share the internal PromptRenderer instance.
    """
    _instance = None

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
        schema = self._renderer.get_minified_schema("task/v1/contents_analysis_schema.jinja2")
        return self._renderer.render(
            "task/v1/contents_analysis.jinja2",
            project_id=project_id,
            response_schema=schema,
            combined_summary=combined_summary
        )