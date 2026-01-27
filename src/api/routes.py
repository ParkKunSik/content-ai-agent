import logging

from fastapi import APIRouter, HTTPException

from src.agent.agent import ContentAnalysisAgent
from src.core.config import settings
from src.schemas.models.api.analyze_request import AnalyzeRequest
from src.schemas.models.api.analyze_response import AnalyzeResponse
from src.schemas.models.prompt.detailed_analysis_response import DetailedAnalysisResponse

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

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    try:
        # Wrap the agent's query method (now async)
        result = await agent.query(
            project_id=request.project_id,
            project_type=request.project_type,
            analysis_mode=request.analysis_mode,
            contents=request.contents
        )
        return result
    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detailed-analysis", response_model=DetailedAnalysisResponse)
async def detailed_analysis(request: AnalyzeRequest):
    """
    Executes the 2-step detailed analysis.
    Accepts project_id and a list of contents (strings or ContentItem objects).
    Returns the detailed analysis with refined summaries.
    """
    try:
        result = await agent.detailed_analysis(
            project_id=request.project_id,
            project_type=request.project_type,
            contents=request.contents,
            analysis_mode=request.analysis_mode
        )
        return result
    except Exception as e:
        logger.error(f"Detailed Analysis API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
