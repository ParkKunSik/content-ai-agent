"""Viewer API 라우터"""

import logging
import sys
from pathlib import Path

# viewer 패키지 경로를 sys.path에 추가
_viewer_root = Path(__file__).parent.parent.parent
if str(_viewer_root) not in sys.path:
    sys.path.insert(0, str(_viewer_root))

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from viewer.schemas.enums import ContentType
from viewer.services.data_service import ViewerDataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/viewer", tags=["viewer"])

# 템플릿 디렉토리 설정
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# 페이지당 프로젝트 수
PAGE_SIZE = 20


def get_content_type_description(content_type_name: str) -> str:
    """Content Type 이름으로 description 조회"""
    try:
        return ContentType[content_type_name].description
    except KeyError:
        return content_type_name


def get_service(provider: str = None):
    """ViewerDataService 인스턴스 생성

    Args:
        provider: "vertex-ai" 또는 "openai", None이면 기존 alias 사용
    """
    try:
        return ViewerDataService(provider=provider)
    except Exception as e:
        logger.error(f"Failed to initialize ViewerDataService: {e}")
        return None


@router.get("/health", include_in_schema=False)
async def health():
    """헬스체크"""
    return "OK"


# =============================================================================
# Provider별 라우트 (Vertex AI, OpenAI)
# 주의: 구체적인 경로를 와일드카드 경로(/{project_id})보다 먼저 정의해야 함
# =============================================================================

@router.get("/vertex-ai", response_class=HTMLResponse, name="viewer_vertex_ai_list")
@router.get("/vertex-ai/", response_class=HTMLResponse, name="viewer_vertex_ai_list_slash")
async def viewer_vertex_ai_list(request: Request, page: int = 1):
    """Vertex AI 분석 결과 목록 페이지"""
    return await _viewer_list_by_provider(request, "vertex-ai", page)


@router.get("/vertex-ai/{project_id}", response_class=HTMLResponse, name="viewer_vertex_ai_detail")
async def viewer_vertex_ai_detail(
    request: Request,
    project_id: int,
    content_type: str = "REVIEW"
):
    """Vertex AI 분석 결과 상세 페이지"""
    return await _viewer_detail_by_provider(request, "vertex-ai", project_id, content_type)


@router.get("/openai", response_class=HTMLResponse, name="viewer_openai_list")
@router.get("/openai/", response_class=HTMLResponse, name="viewer_openai_list_slash")
async def viewer_openai_list(request: Request, page: int = 1):
    """OpenAI 분석 결과 목록 페이지"""
    return await _viewer_list_by_provider(request, "openai", page)


@router.get("/openai/{project_id}", response_class=HTMLResponse, name="viewer_openai_detail")
async def viewer_openai_detail(
    request: Request,
    project_id: int,
    content_type: str = "REVIEW"
):
    """OpenAI 분석 결과 상세 페이지"""
    return await _viewer_detail_by_provider(request, "openai", project_id, content_type)


# =============================================================================
# 기본 라우트 (와일드카드 경로는 맨 마지막에 정의)
# =============================================================================

@router.get("", response_class=HTMLResponse, name="viewer_list")
@router.get("/", response_class=HTMLResponse, name="viewer_list_slash")
async def viewer_list(request: Request, page: int = 1, provider: str = None):
    """프로젝트 목록 페이지 (페이징 지원)

    Args:
        page: 페이지 번호
        provider: "vertex-ai" 또는 "openai", None이면 기존 alias 사용
    """
    service = get_service(provider=provider)

    if service is None:
        return templates.TemplateResponse("viewer_error.html", {
            "request": request,
            "error": "ES 연결에 실패했습니다. 설정을 확인해주세요."
        })

    # 전체 프로젝트 정보 조회 (배치 쿼리로 최적화)
    all_projects = service.get_all_projects_with_info()

    if not all_projects:
        return templates.TemplateResponse("viewer_list.html", {
            "request": request,
            "projects": [],
            "page": 1,
            "total_pages": 0,
            "total_count": 0,
            "provider": provider
        })

    # 페이징 계산
    total_count = len(all_projects)
    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_projects = all_projects[start_idx:end_idx]

    return templates.TemplateResponse("viewer_list.html", {
        "request": request,
        "projects": page_projects,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "provider": provider
    })


@router.get("/{project_id}", response_class=HTMLResponse, name="viewer_detail")
async def viewer_detail(
    request: Request,
    project_id: int,
    content_type: str = "REVIEW",
    provider: str = None
):
    """프로젝트 분석 결과 상세 페이지

    Args:
        project_id: 프로젝트 ID
        content_type: 콘텐츠 타입 (REVIEW, QNA 등)
        provider: "vertex-ai" 또는 "openai", None이면 기존 alias 사용
    """
    service = get_service(provider=provider)

    if service is None:
        return templates.TemplateResponse("viewer_error.html", {
            "request": request,
            "error": "ES 연결에 실패했습니다. 설정을 확인해주세요."
        })

    # 프로젝트 정보 및 content_types 먼저 조회
    project_info = service.get_project_info(project_id)
    content_types = service.get_content_types_by_project(str(project_id))

    # content_type이 해당 프로젝트에 없으면 첫 번째 content_type으로 fallback
    if content_type not in content_types and content_types:
        content_type = content_types[0]
        logger.info(f"Content type fallback to {content_type} for project {project_id}")

    # 데이터 조회
    result_doc = service.get_result(str(project_id), content_type)

    # 전체 프로젝트 정보 조회 (combobox용, 배치 쿼리로 최적화)
    all_projects = service.get_all_projects_with_info()

    if not result_doc or not result_doc.result or not result_doc.result.data:
        return templates.TemplateResponse("viewer_error.html", {
            "request": request,
            "error": "분석 결과가 없습니다."
        })

    # content_type description 조회
    content_type_description = get_content_type_description(content_type)

    # 전체 항목 수 계산
    categories = result_doc.result.data.categories
    total_items = sum(cat.positive_count + cat.negative_count for cat in categories)

    return templates.TemplateResponse("viewer.html", {
        "request": request,
        "project_id": project_id,
        "project_info": project_info,
        "content_type": content_type,
        "content_type_description": content_type_description,
        "content_types": content_types,
        "result": result_doc.result.data,
        "total_items": total_items,
        "updated_at": str(result_doc.updated_at)[:19] if result_doc.updated_at else "N/A",
        "all_projects": all_projects,
        "provider": provider
    })


async def _viewer_list_by_provider(request: Request, provider: str, page: int = 1):
    """Provider별 프로젝트 목록 (내부 공통 함수)"""
    service = get_service(provider=provider)

    if service is None:
        return templates.TemplateResponse("viewer_error.html", {
            "request": request,
            "error": "ES 연결에 실패했습니다. 설정을 확인해주세요."
        })

    # 전체 프로젝트 정보 조회
    all_projects = service.get_all_projects_with_info()

    if not all_projects:
        return templates.TemplateResponse("viewer_list.html", {
            "request": request,
            "projects": [],
            "page": 1,
            "total_pages": 0,
            "total_count": 0,
            "provider": provider
        })

    # 페이징 계산
    total_count = len(all_projects)
    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_projects = all_projects[start_idx:end_idx]

    return templates.TemplateResponse("viewer_list.html", {
        "request": request,
        "projects": page_projects,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "provider": provider
    })


async def _viewer_detail_by_provider(
    request: Request,
    provider: str,
    project_id: int,
    content_type: str = "REVIEW"
):
    """Provider별 프로젝트 상세 (내부 공통 함수)"""
    service = get_service(provider=provider)

    if service is None:
        return templates.TemplateResponse("viewer_error.html", {
            "request": request,
            "error": "ES 연결에 실패했습니다. 설정을 확인해주세요."
        })

    # 프로젝트 정보 및 content_types 조회
    project_info = service.get_project_info(project_id)
    content_types = service.get_content_types_by_project(str(project_id))

    # content_type fallback
    if content_type not in content_types and content_types:
        content_type = content_types[0]
        logger.info(f"Content type fallback to {content_type} for project {project_id}")

    # 데이터 조회
    result_doc = service.get_result(str(project_id), content_type)

    # 전체 프로젝트 정보 조회 (combobox용)
    all_projects = service.get_all_projects_with_info()

    if not result_doc or not result_doc.result or not result_doc.result.data:
        return templates.TemplateResponse("viewer_error.html", {
            "request": request,
            "error": "분석 결과가 없습니다."
        })

    # content_type description 조회
    content_type_description = get_content_type_description(content_type)

    # 전체 항목 수 계산
    categories = result_doc.result.data.categories
    total_items = sum(cat.positive_count + cat.negative_count for cat in categories)

    return templates.TemplateResponse("viewer.html", {
        "request": request,
        "project_id": project_id,
        "project_info": project_info,
        "content_type": content_type,
        "content_type_description": content_type_description,
        "content_types": content_types,
        "result": result_doc.result.data,
        "total_items": total_items,
        "updated_at": str(result_doc.updated_at)[:19] if result_doc.updated_at else "N/A",
        "all_projects": all_projects,
        "provider": provider
    })
