"""
Content Analysis Viewer - Streamlit 앱

ES에 저장된 콘텐츠 분석 결과를 시각화하는 로컬 뷰어입니다.

실행 방법:
    pip install -e ".[viewer]"
    streamlit run src/viewer/app.py --server.port 8501
"""
import logging

import streamlit as st

from src.schemas.enums.content_type import ExternalContentType
from src.viewer.refine_result_renderer import RefineResultRenderer
from src.viewer.viewer_data_service import ViewerDataService

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="Content Analysis Viewer",
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


def main():
    # 헤더
    st.title("📊 Content Analysis Viewer")
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

    # 컨트롤 패널
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        # Project ID Dropdown
        project_ids = service.get_project_ids()
        if not project_ids:
            st.warning("저장된 분석 결과가 없습니다.")
            return

        selected_project = st.selectbox(
            "Project ID",
            project_ids,
            index=0,
            help="분석 결과가 있는 프로젝트 목록입니다.",
        )

    with col2:
        # Content Type Dropdown (project_id에 따라 동적 변경)
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
                    "Content Type",
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
            st.rerun()

    # 구분선
    st.divider()

    # 결과 조회 및 렌더링
    if selected_project and selected_content_type:
        with st.spinner("분석 결과를 조회하는 중..."):
            result_doc = service.get_result(selected_project, selected_content_type)
            # 프로젝트 정보 조회 (Wadiz API)
            project_info = service.get_project_info(int(selected_project))

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
