import logging
import json
from typing import List, Union

from src.core.config import settings
from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.api.analyze_response import AnalyzeResponse
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.prompt.detailed_analysis_response import DetailedAnalysisResponse
from src.services.llm_service import LLMService
from src.services.memory import MemoryService
from src.services.request_content_loader import RequestContentLoader
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
        project_id: int,
        project_type: ProjectType,
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
            result_raw = await self.llm_service.run_single_pass_analysis(contents, analysis_mode.persona_type, project_id, project_type)
        else:
            logger.info("Strategy: Map-Reduce")
            result_raw = await self.llm_service.run_map_reduce_analysis(contents, analysis_mode.persona_type, project_id, project_type)

        # 5. Extract Summary from JSON
        summary_text = self.llm_service._parse_summary(result_raw)

        # 6. Structure Response
        response = AnalyzeResponse(
            project_id=project_id,
            project_type=project_type,
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
        self.memory.save_history(project_id, analysis_mode.value, json.loads(response.model_dump_json()))

        return response

    async def detailed_analysis(
        self, 
        project_id: int,
        project_type: ProjectType,
        contents: List[Union[str, ContentItem]],
        analysis_mode: AnalysisMode
    ) -> DetailedAnalysisResponse:
        """
        Performs a detailed 2-step analysis:
        Step 1: Structure & Extract (Main Analysis)
        Step 2: Refine & Summarize (Optimization)
        Returns base analysis data updated with refined summaries from refinement step.
        """
        logger.info(f"Starting detailed analysis for Project: {project_id}, Mode: {analysis_mode}")
        
        # 1. Preprocess contents
        content_items = self._preprocess_contents(contents)
        
        # 2. Step 1: Main Analysis (PRO_DATA_ANALYST)
        logger.info("Executing Step 1: Main Analysis")
        base_analysis = await self.llm_service.perform_detailed_analysis(
            project_id=project_id,
            project_type=project_type,
            content_items=[item.model_dump() for item in content_items]
        )
        logger.info(f"Step 1 completed. Categories found: {len(base_analysis.categories)}")
        
        # 3. Step 2: Refine Summary
        # Uses the persona defined in AnalysisMode for refinement
        logger.info(f"Executing Step 2: Refinement with persona {analysis_mode.persona_type}")
        refinement_result = await self.llm_service.refine_analysis_summary(
            project_id=project_id,
            project_type=project_type,
            raw_analysis_data=base_analysis.model_dump_json(),
            persona_type=analysis_mode.persona_type
        )
        
        # 4. Merge Refined Summaries into Base Analysis
        base_analysis.summary = refinement_result.summary
        
        # Create a lookup map for refined category summaries
        refined_map = {cat.category_key: cat.summary for cat in refinement_result.categories}
        
        for category in base_analysis.categories:
            if category.category_key in refined_map:
                category.summary = refined_map[category.category_key]
        
        # 5. Archive final merged result
        try:
            self.memory.save_history(
                project_id=project_id,
                persona_type=analysis_mode.value,
                result_data=json.loads(base_analysis.model_dump_json())
            )
        except Exception as e:
            logger.warning(f"Failed to save detailed analysis history: {e}")

        logger.info("Detailed analysis completed successfully")
        
        return base_analysis

    def _preprocess_contents(self, contents: List[Union[str, ContentItem]]) -> List[ContentItem]:
        """Converts raw strings to ContentItem objects if necessary."""
        processed = []
        for idx, item in enumerate(contents):
            if isinstance(item, str):
                # Generate a temporary ID for string inputs
                processed.append(ContentItem(content_id=idx + 1, content=item))
            elif isinstance(item, ContentItem):
                processed.append(item)
            else:
                logger.warning(f"Skipping invalid content type: {type(item)}")
        return processed