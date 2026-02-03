import logging

from fastapi import APIRouter, HTTPException

from src.agent.agent import ContentAnalysisAgent
from src.core.config import settings
from src.schemas.models.api.analyze_request import AnalyzeRequest
from src.schemas.models.prompt.structured_analysis_response import StructuredAnalysisResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Agent for Local Testing
# This instance will be shared across requests
agent = ContentAnalysisAgent()
# Explicitly call set_up as required by the new Agent pattern
try:
    agent.set_up()
except Exception as e:
    logger.error(f"Failed to setup agent: {e}")

@router.get("/health")
def health_check():
    return {"status": "healthy", "env": settings.ENV}

@router.post("/analysis", response_model=StructuredAnalysisResponse)
async def analysis(request: AnalyzeRequest):
    """
    Executes the 2-step detailed analysis.
    Accepts project_id and a list of contents (strings or ContentItem objects).
    Returns the detailed analysis with refined summaries.
    """
    try:
        result = await agent.analysis(
            project_id=request.project_id,
            project_type=request.project_type,
            contents=request.contents,
            analysis_mode=request.analysis_mode
        )
        return result
    except Exception as e:
        logger.error(f"Detailed Analysis API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
