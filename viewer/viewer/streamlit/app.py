"""
커뮤니티 요약 뷰어 - Streamlit 앱

ES에 저장된 콘텐츠 분석 결과를 시각화하는 로컬 뷰어입니다.

실행:
    cd viewer
    pip install -e ".[streamlit]"
    streamlit run viewer/streamlit/app.py --server.port 8701
"""
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

# viewer 패키지 경로를 sys.path에 추가
_viewer_root = Path(__file__).parent.parent.parent
if str(_viewer_root) not in sys.path:
    sys.path.insert(0, str(_viewer_root))

import streamlit as st

from viewer.schemas.enums import ContentType
from viewer.schemas.models import CompareProjectItem, CompareStats, ProjectInfo, ResultDocument
from viewer.services.data_service import ViewerDataService
from viewer.streamlit.renderer import RefineResultRenderer

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
        return ContentType[content_type_name].description
    except KeyError:
        return content_type_name


def get_service(provider: str = None):
    """ViewerDataService 인스턴스 생성

    Args:
        provider: "vertex-ai" 또는 "openai", None이면 기존 alias 사용

    Note:
        provider별로 다른 ES alias를 사용하므로 캐싱하지 않음
    """
    try:
        service = ViewerDataService(provider=provider)
        logger.info(f"ViewerDataService created with provider={provider}, alias={service.result_index_alias}")
        return service
    except Exception as e:
        logger.error(f"Failed to initialize ViewerDataService: {e}")
        return None


@st.cache_data(ttl=3600)
def get_project_info_map(project_ids: tuple) -> Dict[str, Optional[ProjectInfo]]:
    """
    프로젝트 ID 목록에 대한 ProjectInfo 매핑을 캐싱하여 반환

    Args:
        project_ids: 프로젝트 ID 튜플 (캐싱 키로 사용)

    Returns:
        {project_id: ProjectInfo} 딕셔너리

    Note:
        ProjectInfo는 Wadiz API에서 조회하므로 provider와 무관합니다.
    """
    result = {}
    for pid in project_ids:
        try:
            info = ViewerDataService.get_project_info(int(pid))
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


def render_llm_usage(result_doc: ResultDocument, provider_name: str):
    """LLM 사용량 렌더링"""
    if not result_doc.llm_usages:
        return

    with st.expander(f"📊 LLM 사용량 ({provider_name})", expanded=False):
        total_input = 0
        total_output = 0
        total_cost = 0.0
        total_duration = 0

        for usage in result_doc.llm_usages:
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            with col1:
                st.write(f"**Step {usage.step}**: {usage.model}")
            with col2:
                st.write(f"In: {usage.input_tokens:,} / Out: {usage.output_tokens:,}")
            with col3:
                if usage.total_cost:
                    st.write(f"${usage.total_cost:.4f}")
            with col4:
                st.write(f"{usage.duration_ms:,}ms")

            total_input += usage.input_tokens
            total_output += usage.output_tokens
            total_cost += usage.total_cost or 0
            total_duration += usage.duration_ms

        st.divider()
        total_tokens = total_input + total_output
        st.write(f"**합계**: {total_tokens:,} tokens (In: {total_input:,} / Out: {total_output:,})")
        if total_cost > 0:
            st.write(f"**비용**: ${total_cost:.4f} | **소요시간**: {total_duration:,}ms")
        else:
            st.write(f"**소요시간**: {total_duration:,}ms")


def render_stats_view(stats: CompareStats):
    """전체 Provider 비교 통계 렌더링 (HTML 렌더러 사용)"""
    # HTML 렌더러로 통계 뷰 생성
    html_content = RefineResultRenderer.generate_stats_html(stats)

    # HTML 컴포넌트로 렌더링
    st.components.v1.html(html_content, height=900, scrolling=True)


def render_single_result(result_doc: ResultDocument, project_info: Optional[ProjectInfo],
                         content_type: str, content_type_desc: str, provider_name: str = None):
    """단일 Provider 결과 렌더링"""
    if not result_doc or not result_doc.result or not result_doc.result.data:
        st.warning("분석 결과 데이터가 없습니다.")
        return

    # LLM 사용량 표시
    render_llm_usage(result_doc, provider_name or "LLM")

    # HTML 생성 및 렌더링
    html_content = RefineResultRenderer.generate_amazon_style_html(
        result=result_doc.result.data,
        project_id=int(result_doc.project_id),
        content_type=content_type,
        executed_at=str(result_doc.updated_at)[:19] if result_doc.updated_at else "N/A",
        content_type_description=content_type_desc,
        project_title=project_info.title if project_info else None,
        project_thumbnail_url=project_info.thumbnail_url if project_info else None,
        project_link=project_info.link if project_info else None,
    )

    # HTML 컴포넌트로 렌더링
    st.components.v1.html(html_content, height=800, scrolling=True)


def render_compare_view(vertex_doc: Optional[ResultDocument], openai_doc: Optional[ResultDocument],
                        project_info: Optional[ProjectInfo], project_id: int, content_type_desc: str):
    """비교 뷰 렌더링 (HTML 렌더러 사용 - viewer와 동일한 UI)"""

    # 양쪽 모두 없으면 경고
    if not vertex_doc and not openai_doc:
        st.warning("양쪽 모두 분석 결과가 없습니다.")
        return

    # HTML 렌더러로 비교 뷰 생성
    html_content = RefineResultRenderer.generate_compare_html(
        vertex_doc=vertex_doc,
        openai_doc=openai_doc,
        project_id=project_id,
        content_type_description=content_type_desc
    )

    # HTML 컴포넌트로 렌더링
    st.components.v1.html(html_content, height=1200, scrolling=True)


def main():
    # 헤더
    st.title("📊 커뮤니티 요약 뷰어")
    st.caption("Elasticsearch에 저장된 콘텐츠 분석 결과를 조회합니다.")

    # 사이드바 설정
    with st.sidebar:
        st.header("🔧 설정")

        # 뷰 모드 선택
        view_mode = st.radio(
            "📋 보기 모드",
            ["단일 Provider", "비교 모드", "통계"],
            index=0,
            help="단일: Provider별 조회, 비교: Vertex AI vs OpenAI, 통계: 전체 LLM 사용량"
        )

        st.divider()

        compare_mode = view_mode == "비교 모드"
        stats_mode = view_mode == "통계"

        if view_mode == "단일 Provider":
            # 단일 Provider 선택
            provider_options = {
                "기본 (통합)": None,
                "Vertex AI": "vertex-ai",
                "OpenAI": "openai",
            }
            selected_provider_label = st.radio(
                "LLM Provider",
                list(provider_options.keys()),
                index=0,
                help="분석에 사용된 LLM Provider를 선택합니다.",
            )
            selected_provider = provider_options[selected_provider_label]

            if selected_provider:
                st.info(f"📡 {selected_provider_label} 분석 결과 조회 중")
        elif compare_mode:
            selected_provider = None
            st.success("🔀 Vertex AI와 OpenAI 결과를 비교합니다.")
        else:
            # 통계 모드
            selected_provider = None
            st.info("📊 전체 LLM 사용량 통계를 조회합니다.")

    # === 통계 모드 ===
    if stats_mode:
        with st.spinner("통계 데이터 조회 중..."):
            stats = ViewerDataService.get_compare_stats()

        render_stats_view(stats)
        return

    # === 비교 모드 ===
    if compare_mode:
        # 비교용 프로젝트 목록 조회
        with st.spinner("프로젝트 목록 조회 중..."):
            compare_projects: List[CompareProjectItem] = ViewerDataService.get_all_compare_projects()

        if not compare_projects:
            st.warning("저장된 분석 결과가 없습니다.")
            return

        # 프로젝트 정보 매핑
        project_ids = [p.project_id for p in compare_projects]
        project_info_map = get_project_info_map(tuple(project_ids))

        # 프로젝트 표시명 → 아이템 매핑
        project_display_to_item = {}
        for p in compare_projects:
            info = p.project_info
            display_name = get_project_display_name(p.project_id, info)
            # Provider 상태 표시 추가
            status = ""
            if p.has_vertex_ai and p.has_openai:
                status = " [V+O]"
            elif p.has_vertex_ai:
                status = " [V]"
            elif p.has_openai:
                status = " [O]"
            project_display_to_item[display_name + status] = p

        project_display_names = list(project_display_to_item.keys())

        # 컨트롤 패널
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            selected_display_name = st.selectbox(
                "프로젝트",
                project_display_names,
                index=0,
                help="[V]=Vertex AI, [O]=OpenAI, [V+O]=둘 다",
            )
            selected_item = project_display_to_item[selected_display_name]
            selected_project = selected_item.project_id

        with col2:
            # 통합 content_types 조회
            content_types = ViewerDataService.get_merged_content_types(selected_project)
            if content_types:
                content_type_options = {
                    get_content_type_description(ct): ct for ct in content_types
                }
                selected_desc = st.selectbox(
                    "커뮤니티 댓글 종류",
                    list(content_type_options.keys()),
                    index=0,
                )
                selected_content_type = content_type_options[selected_desc]
                selected_content_type_desc = selected_desc
            else:
                st.warning(f"프로젝트 {selected_project}에 콘텐츠 타입이 없습니다.")
                return

        with col3:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()

        st.divider()

        # 비교 결과 조회
        with st.spinner("분석 결과를 조회하는 중..."):
            compare_result = ViewerDataService.get_compare_result(selected_project, selected_content_type)
            project_info = compare_result.project_info

        # 비교 뷰 렌더링
        render_compare_view(
            compare_result.vertex_ai,
            compare_result.openai,
            project_info,
            int(selected_project),
            selected_content_type_desc
        )

    # === 단일 Provider 모드 ===
    else:
        # 서비스 초기화
        service = get_service(provider=selected_provider)

        if service is None:
            st.error(
                "ES 연결에 실패했습니다. `.env` 파일의 ES 설정을 확인해주세요.\n\n"
                "필요한 설정:\n"
                "- `ES_HOST`\n"
                "- `ES_PORT` (선택)\n"
                "- `ES_USERNAME` (선택)\n"
                "- `ES_PASSWORD` (선택)"
            )
            return

        # 프로젝트 ID 목록 조회
        project_ids = service.get_project_ids()
        if not project_ids:
            st.warning("저장된 분석 결과가 없습니다.")
            return

        # 프로젝트 정보 매핑 조회
        project_info_map = get_project_info_map(tuple(project_ids))

        # 프로젝트 표시명 → ID 매핑 생성
        project_display_to_id = {
            get_project_display_name(pid, project_info_map.get(pid)): pid
            for pid in project_ids
        }
        project_display_names = list(project_display_to_id.keys())

        # 컨트롤 패널
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            selected_display_name = st.selectbox(
                "프로젝트",
                project_display_names,
                index=0,
                help="분석 결과가 있는 프로젝트 목록입니다.",
            )
            selected_project = project_display_to_id[selected_display_name]

        with col2:
            selected_content_type = None
            selected_content_type_desc = None
            if selected_project:
                content_types = service.get_content_types_by_project(selected_project)
                if content_types:
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
            st.write("")
            st.write("")
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()

        st.divider()

        # 결과 조회 및 렌더링
        if selected_project and selected_content_type:
            with st.spinner("분석 결과를 조회하는 중..."):
                result_doc = service.get_result(selected_project, selected_content_type)
                project_info = project_info_map.get(selected_project)

            if result_doc:
                render_single_result(
                    result_doc,
                    project_info,
                    selected_content_type,
                    selected_content_type_desc,
                    selected_provider_label if selected_provider else None
                )
            else:
                st.warning("선택한 조건에 해당하는 분석 결과가 없습니다.")


if __name__ == "__main__":
    main()
