import logging
from fastapi import APIRouter, HTTPException
from src.schemas.models import AnalyzeRequest, AnalyzeResponse
from src.agent.base import ContentAnalysisAgent
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Agent for Local Testing
# This instance will be shared across requests
agent = ContentAnalysisAgent(
    model_pro=settings.VERTEX_AI_MODEL_PRO,
    model_flash=settings.VERTEX_AI_MODEL_FLASH
)

@router.get("/health")
def health_check():
    return {"status": "healthy", "env": settings.ENV}

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    try:
        # Wrap the agent's query method (now async)
        result = await agent.query(
            project_id=request.project_id,
            analysis_mode=request.analysis_mode,
            contents=request.contents
        )
        return result
    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
