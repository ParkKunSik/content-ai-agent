"""
커뮤니티 요약 뷰어 - Streamlit 앱

ES에 저장된 콘텐츠 분석 결과를 시각화하는 로컬 뷰어입니다.

실행 방법:
    pip install -e ".[viewer]"
    streamlit run src/viewer/app.py --server.port 8501
"""
import logging
from typing import Dict, Optional

import streamlit as st

from src.schemas.enums.content_type import ExternalContentType
from src.viewer.refine_result_renderer import RefineResultRenderer
from src.viewer.viewer_data_service import ProjectInfo, ViewerDataService

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="커뮤니티 요약 뷰어",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def get_content_type_description(content_type_name: str) -> str:
    """Content Type 이름으로 description 조회"""
    try:
        return ExternalContentType[content_type_name].description
    except KeyError:
        return content_type_name


@st.cache_resource
def get_service():
    """ViewerDataService 싱글톤 (캐싱)"""
    try:
        return ViewerDataService()
    except Exception as e:
        logger.error(f"Failed to initialize ViewerDataService: {e}")
        return None


@st.cache_data(ttl=3600)
def get_project_info_map(_service: ViewerDataService, project_ids: tuple) -> Dict[str, Optional[ProjectInfo]]:
    """
    프로젝트 ID 목록에 대한 ProjectInfo 매핑을 캐싱하여 반환

    Args:
        _service: ViewerDataService (언더스코어로 해싱 제외)
        project_ids: 프로젝트 ID 튜플 (캐싱 키로 사용)

    Returns:
        {project_id: ProjectInfo} 딕셔너리
    """
    result = {}
    for pid in project_ids:
        try:
            info = _service.get_project_info(int(pid))
            result[pid] = info
        except Exception as e:
            logger.warning(f"Failed to get project info for {pid}: {e}")
            result[pid] = None
    return result


def get_project_display_name(project_id: str, project_info: Optional[ProjectInfo]) -> str:
    """프로젝트 표시명 생성 (제목이 있으면 제목, 없으면 ID)"""
    if project_info and project_info.title:
        return f"{project_info.title} ({project_id})"
    return f"프로젝트 {project_id}"


def main():
    # 헤더
    st.title("📊 커뮤니티 요약 뷰어")
    st.caption("Elasticsearch에 저장된 콘텐츠 분석 결과를 조회합니다.")

    # 서비스 초기화
    service = get_service()

    if service is None:
        st.error(
            "ES 연결에 실패했습니다. `.env.local` 파일의 ES 설정을 확인해주세요.\n\n"
            "필요한 설정:\n"
            "- `ES_MAIN_HOST`\n"
            "- `ES_MAIN_PORT`\n"
            "- `ES_MAIN_USERNAME` (선택)\n"
            "- `ES_MAIN_PASSWORD` (선택)"
        )
        return

    # 프로젝트 ID 목록 조회
    project_ids = service.get_project_ids()
    if not project_ids:
        st.warning("저장된 분석 결과가 없습니다.")
        return

    # 프로젝트 정보 매핑 조회 (캐싱)
    project_info_map = get_project_info_map(service, tuple(project_ids))

    # 프로젝트 표시명 → ID 매핑 생성
    project_display_to_id = {
        get_project_display_name(pid, project_info_map.get(pid)): pid
        for pid in project_ids
    }
    project_display_names = list(project_display_to_id.keys())

    # 컨트롤 패널
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        # 프로젝트 Dropdown (제목으로 표시)
        selected_display_name = st.selectbox(
            "프로젝트",
            project_display_names,
            index=0,
            help="분석 결과가 있는 프로젝트 목록입니다.",
        )
        selected_project = project_display_to_id[selected_display_name]

    with col2:
        # 커뮤니티 댓글 종류 Dropdown (project_id에 따라 동적 변경)
        selected_content_type = None
        selected_content_type_desc = None
        if selected_project:
            content_types = service.get_content_types_by_project(selected_project)
            if content_types:
                # Content Type을 description으로 표시
                content_type_options = {
                    get_content_type_description(ct): ct for ct in content_types
                }
                selected_desc = st.selectbox(
                    "커뮤니티 댓글 종류",
                    list(content_type_options.keys()),
                    index=0,
                    help="선택한 프로젝트의 콘텐츠 타입입니다.",
                )
                selected_content_type = content_type_options[selected_desc]
                selected_content_type_desc = selected_desc
            else:
                st.warning(f"프로젝트 {selected_project}에 콘텐츠 타입이 없습니다.")

    with col3:
        st.write("")  # 간격 조정
        st.write("")
        # Refresh 버튼
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_resource.clear()
            st.cache_data.clear()
            st.rerun()

    # 구분선
    st.divider()

    # 결과 조회 및 렌더링
    if selected_project and selected_content_type:
        with st.spinner("분석 결과를 조회하는 중..."):
            result_doc = service.get_result(selected_project, selected_content_type)
            # 프로젝트 정보는 이미 캐싱된 매핑에서 조회
            project_info = project_info_map.get(selected_project)

        if result_doc:
            # 결과 데이터 확인
            if result_doc.result and result_doc.result.data:
                # HTML 생성 및 렌더링 (content_type_description에 enum description 사용)
                html_content = RefineResultRenderer.generate_amazon_style_html(
                    result=result_doc.result.data,
                    project_id=int(result_doc.project_id),
                    content_type=selected_content_type,
                    executed_at=str(result_doc.updated_at)[:19] if result_doc.updated_at else "N/A",
                    content_type_description=selected_content_type_desc,
                    project_title=project_info.title if project_info else None,
                    project_thumbnail_url=project_info.thumbnail_url if project_info else None,
                    project_link=project_info.link if project_info else None,
                )

                # HTML 컴포넌트로 렌더링
                st.components.v1.html(html_content, height=800, scrolling=True)
            else:
                st.warning("분석 결과 데이터가 없습니다.")
                if result_doc.reason:
                    st.error(f"사유: {result_doc.reason}")
        else:
            st.warning("선택한 조건에 해당하는 분석 결과가 없습니다.")


if __name__ == "__main__":
    main()
