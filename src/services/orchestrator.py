import logging
from typing import List, Union

from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.prompt.structured_analysis_response import StructuredAnalysisResponse
from src.services.llm_service import LLMService
from src.services.request_content_loader import RequestContentLoader
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Coordinates the analysis process by delegating tasks to Specialized Services.
    """

    def __init__(self):
        self.loader = RequestContentLoader()
        self.prompt_manager = PromptManager()
        self.llm_service = LLMService(self.prompt_manager)

    async def analysis(
        self, 
        project_id: int,
        project_type: ProjectType,
        contents: List[Union[str, ContentItem]],
        analysis_mode: AnalysisMode
    ) -> StructuredAnalysisResponse:
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
        base_analysis = await self.llm_service.structure_content_analysis(
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