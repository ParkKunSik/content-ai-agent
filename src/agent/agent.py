import logging
import json
from typing import List, Dict, Any, Union
from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.services.orchestrator import AgentOrchestrator
from src.core.model_factory import ModelFactory

logger = logging.getLogger(__name__)

class ContentAnalysisAgent:
    """
    Vertex AI Reasoning Engine Compatible Agent.
    Serves as the main entry point, delegating logic to the Orchestrator.
    """
    
    def __init__(self):
        """
        Constructor for the agent. 
        Model configuration is handled via settings and ModelFactory during set_up.
        """
        self.orchestrator = None

    def set_up(self):
        """
        Initialization logic called by the Reasoning Engine or Local Wrapper.
        Loads system instructions via ModelFactory.
        """
        logger.info("Setting up ContentAnalysisAgent services...")
        
        # Initialize all models with their versioned system instructions
        ModelFactory.initialize()

        # Initialize Orchestrator
        self.orchestrator = AgentOrchestrator()
        logger.info("Agent setup complete.")

    async def query(
        self, 
        project_id: int,
        project_type: ProjectType,
        analysis_mode: AnalysisMode, 
        contents: List[str]
    ) -> Dict[str, Any]:
        """
        Main query method. Executes the analysis pipeline.
        """
        if not self.orchestrator:
            raise RuntimeError("Agent not set up. Call set_up() before query().")

        try:
            response_model = await self.orchestrator.orchestrate_analysis(
                project_id=project_id,
                project_type=project_type,
                analysis_mode=analysis_mode,
                content_sources=contents
            )
            return json.loads(response_model.model_dump_json())

        except Exception as e:
            logger.error(f"Error during agent query: {e}")
            raise

    async def detailed_analysis(
        self,
        project_id: int,
        project_type: ProjectType,
        contents: List[Union[str, ContentItem]],
        analysis_mode: AnalysisMode = AnalysisMode.DATA_ANALYST
    ) -> Dict[str, Any]:
        """
        Executes the detailed analysis pipeline (2-step).
        """
        if not self.orchestrator:
            raise RuntimeError("Agent not set up. Call set_up() before detailed_analysis().")

        try:
            response_model = await self.orchestrator.detailed_analysis(
                project_id=project_id,
                project_type=project_type,
                contents=contents,
                analysis_mode=analysis_mode
            )
            return json.loads(response_model.model_dump_json())
        except Exception as e:
            logger.error(f"Error during detailed analysis: {e}")
            raise