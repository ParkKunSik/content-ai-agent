import logging

from fastapi import APIRouter, HTTPException

from src.agent.agent import ContentAnalysisAgent
from src.core.config import settings
from src.schemas.models.api.analyze_request import AnalyzeRequest
from src.schemas.models.api.project_analysis_request import ProjectAnalysisRequest
from src.schemas.models.common.structured_analysis_refine_result import StructuredAnalysisRefineResult
from src.services.orchestrator import AgentOrchestrator

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

# Initialize Orchestrator (ES manager auto-initialized inside)
orchestrator = AgentOrchestrator()

@router.get("/health")
def health_check():
    return {"status": "healthy", "env": settings.ENV}

@router.post("/analysis", response_model=StructuredAnalysisRefineResult)
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

@router.post("/project-analysis", response_model=StructuredAnalysisRefineResult)
async def project_analysis(request: ProjectAnalysisRequest):
    """
    프로젝트 기반 콘텐츠 분석 API
    
    - Elasticsearch에서 프로젝트 콘텐츠 조회
    - AI 분석 수행
    - force_refresh 옵션: 향후 캐시 기능을 위한 placeholder
    """
    try:
        logger.info(f"Project analysis requested - Project: {request.project_id}, Content Type: {request.content_type}")
        
        # 오케스트레이터를 통한 분석 수행
        analysis_result = await orchestrator.project_analysis(
            project_id=request.project_id,
            project_type=request.project_type,
            content_type=request.content_type,
            analysis_mode=request.analysis_mode
        )
        
        logger.info(f"Project analysis completed successfully for project {request.project_id}")
        return analysis_result
            
    except Exception as e:
        logger.error(f"Project Analysis API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
