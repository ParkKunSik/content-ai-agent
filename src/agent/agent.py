import logging
from typing import List, Optional

from src.core.session_factory import SessionFactory
from src.schemas.enums.analysis_mode import AnalysisMode
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.es.content_analysis_result import ContentAnalysisResultDataV1
from src.services.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)


class ContentAnalysisAgent:
    """
    Vertex AI Reasoning Engine Compatible Agent.
    Serves as the main entry point, delegating logic to the Orchestrator.
    """

    def __init__(self):
        """
        Constructor for the agent.
        Model configuration is handled via settings and SessionFactory during set_up.
        """
        self.orchestrator = None

    def set_up(self):
        """
        Initialization logic called by the Reasoning Engine or Local Wrapper.
        Loads system instructions via SessionFactory.
        """
        logger.info("Setting up ContentAnalysisAgent services...")

        # Initialize all models with their versioned system instructions
        SessionFactory.initialize()

        # Initialize Orchestrator
        self.orchestrator = AgentOrchestrator()
        logger.info("Agent setup complete.")

    async def analysis(
        self,
        project_id: int,
        project_type: ProjectType,
        contents: List[ContentItem],
        analysis_mode: AnalysisMode = AnalysisMode.REVIEW_BOT,
        content_type: Optional[ExternalContentType] = None
    ) -> ContentAnalysisResultDataV1:
        """
        Executes the detailed analysis pipeline (2-step).

        Args:
            contents: List of ContentItem objects (content_id required for traceability)
        """
        if not self.orchestrator:
            raise RuntimeError("Agent not set up. Call set_up() before detailed_analysis().")

        try:
            return await self.orchestrator.analysis(
                project_id=project_id,
                project_type=project_type,
                contents=contents,
                analysis_mode=analysis_mode,
                content_type=content_type
            )
        except Exception as e:
            logger.error(f"Error during detailed analysis: {e}")
            raise