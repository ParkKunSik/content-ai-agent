import logging
from typing import List

from src.core.config import settings
from src.schemas.enums import AnalysisMode
from src.schemas.models import AnalyzeResponse
from src.services.memory import MemoryService
from src.services.request_content_loader import RequestContentLoader
from src.services.llm_service import LLMService
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# Constants for Hybrid Strategy
ROUTING_THRESHOLD = 500000  # 500k tokens

class AgentOrchestrator:
    """
    Coordinates the analysis process by delegating tasks to Specialized Services.
    """

    def __init__(self):
        self.loader = RequestContentLoader()
        self.memory = MemoryService()
        self.prompt_manager = PromptManager()
        self.llm_service = LLMService(self.prompt_manager)

    async def orchestrate_analysis(
        self,
        project_id: str,
        analysis_mode: AnalysisMode,
        content_sources: List[str]
    ) -> AnalyzeResponse:
        """
        Main entry point for analysis.
        """
        logger.info(f"Starting analysis for Project: {project_id}, Mode: {analysis_mode}")

        # 1. Validate file sizes
        validation_result = self.loader.validate_file_sizes(content_sources)
        if not validation_result.is_valid:
            invalid_files = [result.source for result in validation_result.results if not result.is_valid]
            raise ValueError(
                f"File size validation failed. Files exceeding {validation_result.max_size_bytes} bytes: {invalid_files}"
            )
        
        # 2. Load Content
        contents = self.loader.load_all(content_sources)
        if not contents:
            raise ValueError("No content could be loaded from the provided sources.")

        # 3. Calculate Tokens
        total_tokens = await self.llm_service.count_total_tokens(contents)
        logger.info(f"Total tokens: {total_tokens}")

        # 4. Routing & Analysis
        if total_tokens < ROUTING_THRESHOLD:
            logger.info("Strategy: Single Pass")
            result_raw = await self.llm_service.run_single_pass_analysis(contents, analysis_mode.persona_type, project_id)
        else:
            logger.info("Strategy: Map-Reduce")
            result_raw = await self.llm_service.run_map_reducㅠe_analysis(contents, analysis_mode.persona_type, project_id)

        # 5. Extract Summary from JSON
        summary_text = self.llm_service._parse_summary(result_raw)

        # 6. Structure Response
        response = AnalyzeResponse(
            project_id=project_id,
            analysis_mode=analysis_mode,
            summary=summary_text,
            keywords=[], 
            insights=[],
            metadata={
                "strategy": "map-reduce" if total_tokens >= ROUTING_THRESHOLD else "single-pass",
                "total_tokens": total_tokens,
                "agent_id": settings.INTERNAL_AGENT_ID
            }
        )

        # 7. Archive
        self.memory.save_history(project_id, analysis_mode.value, response.model_dump())

        return response