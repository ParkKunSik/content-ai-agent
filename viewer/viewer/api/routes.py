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


def get_service():
    """ViewerDataService 인스턴스 생성"""
    try:
        return ViewerDataService()
    except Exception as e:
        logger.error(f"Failed to initialize ViewerDataService: {e}")
        return None


@router.get("/health", include_in_schema=False)
async def health():
    """헬스체크"""
    return "OK"


@router.get("/", response_class=HTMLResponse, name="viewer_list")
async def viewer_list(request: Request, page: int = 1):
    """프로젝트 목록 페이지 (페이징 지원)"""
    service = get_service()

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
            "total_count": 0
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
        "total_count": total_count
    })


@router.get("/{project_id}", response_class=HTMLResponse, name="viewer_detail")
async def viewer_detail(
    request: Request,
    project_id: int,
    content_type: str = "REVIEW"
):
    """프로젝트 분석 결과 상세 페이지"""
    service = get_service()

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
        "all_projects": all_projects
    })
