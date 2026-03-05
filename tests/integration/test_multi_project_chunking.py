"""
Multi-Project 배치 분석 통합 테스트

테스트 시나리오:
1. Multi-Project 순차 청킹 시뮬레이션
2. 프로젝트별 독립 청킹 및 완료 제외 로직
3. Provider별 테스트 (Vertex AI, Gemini API, OpenAI)
4. 결과 출력 (JSON + HTML)
5. 특정 기간 데이터 기반 테스트 데이터 셋 생성

설계 문서: documents/multi-project-batch-analysis-test-design.md
"""
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pytest

from src.core.config.settings import settings
from src.core.llm.enums import ProviderType
from src.core.llm.registry import ProviderRegistry
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.common.llm_usage_info import LLMUsageInfo
from src.schemas.models.prompt.analysis_content_item import AnalysisContentItem
from src.schemas.models.prompt.multi_project_batch_item import MultiProjectBatchItem
from src.schemas.models.prompt.multi_project_summary_item import MultiProjectSummaryItem
from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult
from src.schemas.models.prompt.structured_analysis_summary import CategorySummaryItem, StructuredAnalysisSummary
from src.services.es_content_retrieval_service import ESContentRetrievalService
from src.services.llm_service import LLMService
from src.utils.generation_viewer import GenerationViewer
from src.utils.llm_usage_aggregator import merge_llm_usage_lists
from src.utils.prompt_manager import PromptManager


# ============================================================
# 테스트 데이터 구조
# ============================================================

@dataclass
class MultiProjectTestItem:
    """테스트 대상 단일 프로젝트"""
    project_id: int
    project_type: ProjectType
    content_type: ExternalContentType
    content_items: Optional[List[ContentItem]] = None  # pre-loaded 콘텐츠 (기간 기반 테스트용)


@dataclass
class MultiProjectTestInput:
    """테스트 입력 전체"""
    projects: List[MultiProjectTestItem]
    chunk_size: int = 100
    max_chunks: Optional[int] = None
    max_items_per_project: Optional[int] = None  # 프로젝트당 최대 콘텐츠 수


@dataclass
class ProjectChunkingState:
    """프로젝트별 청킹 상태 추적"""
    project_id: int
    project_type: ProjectType
    content_type: ExternalContentType
    all_content_items: List[ContentItem] = field(default_factory=list)
    all_chunks: List[List[ContentItem]] = field(default_factory=list)
    current_chunk_idx: int = 0
    accumulated_result: Optional[StructuredAnalysisResult] = None

    def has_remaining_chunks(self) -> bool:
        """남은 청크가 있는지 확인"""
        return self.current_chunk_idx < len(self.all_chunks)

    def get_current_chunk(self) -> List[ContentItem]:
        """현재 청크 반환"""
        if self.has_remaining_chunks():
            return self.all_chunks[self.current_chunk_idx]
        return []

    def advance_chunk(self):
        """다음 청크로 이동"""
        self.current_chunk_idx += 1

    @property
    def total_content_count(self) -> int:
        return len(self.all_content_items)

    @property
    def chunks_used(self) -> int:
        return self.current_chunk_idx


@dataclass
class MultiProjectTestOutput:
    """테스트 출력"""
    results: Dict[int, StructuredAnalysisResult]
    llm_usages: List[LLMUsageInfo]
    total_chunks_processed: int
    total_content_items: int
    per_project_stats: List[dict]


# ============================================================
# Helper Functions
# ============================================================

def _format_duration(seconds: float) -> str:
    """초 단위 시간을 HH:MM:SS.sss 형태로 변환"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def _convert_kst_to_utc(kst_datetime_str: str) -> str:
    """
    KST(한국 표준시) 문자열을 UTC 문자열로 변환.

    Args:
        kst_datetime_str: KST 일시 문자열 (ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)
                          예시: "2026-03-04T09:00:00"

    Returns:
        UTC 일시 문자열 (ISO 8601 형식)
        예시: "2026-03-04T00:00:00" (KST 09:00 → UTC 00:00)

    Note:
        KST = UTC + 9시간
        따라서 KST에서 9시간을 빼면 UTC가 됨
    """
    kst_dt = datetime.strptime(kst_datetime_str, '%Y-%m-%dT%H:%M:%S')
    utc_dt = kst_dt - timedelta(hours=9)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%S')


@contextmanager
def switch_llm_provider(provider: ProviderType):
    """LLM Provider를 임시로 변경하는 Context Manager"""
    original_provider = settings.llm_provider
    original_initialized = ProviderRegistry._initialized.copy()
    original_current = ProviderRegistry._current_provider
    try:
        settings.llm_provider = provider
        ProviderRegistry._initialized = {k: False for k in ProviderRegistry._initialized}
        ProviderRegistry._current_provider = None
        print(f"\n🔄 LLM Provider 변경: {original_provider.value} → {provider.value}")
        yield
    finally:
        settings.llm_provider = original_provider
        ProviderRegistry._initialized = original_initialized
        ProviderRegistry._current_provider = original_current


def _split_chunks(content_items: List[ContentItem], chunk_size: int) -> List[List[ContentItem]]:
    """콘텐츠를 청크로 분할"""
    return [content_items[i:i + chunk_size] for i in range(0, len(content_items), chunk_size)]


def _convert_to_analysis_items(content_items: List[ContentItem]) -> List[AnalysisContentItem]:
    """ContentItem을 AnalysisContentItem으로 변환"""
    return [
        AnalysisContentItem(
            id=item.content_id,
            content=item.content,
            has_image=item.has_image if item.has_image else None
        )
        for item in content_items
    ]


def _to_summary(result: StructuredAnalysisResult) -> StructuredAnalysisSummary:
    """StructuredAnalysisResult를 StructuredAnalysisSummary로 변환"""
    return StructuredAnalysisSummary(
        summary=result.summary,
        keywords=result.keywords,
        good_points=result.good_points,
        caution_points=result.caution_points,
        categories=[
            CategorySummaryItem(key=cat.key, summary=cat.summary, keywords=cat.keywords)
            for cat in result.categories
        ]
    )


# ============================================================
# ES 데이터 로드
# ============================================================

async def _load_project_content_items(
    project_id: int,
    project_type: ProjectType,
    content_type: ExternalContentType
) -> List[ContentItem]:
    """ES에서 프로젝트 콘텐츠 로드"""
    es_service = ESContentRetrievalService()

    print(f"   - ES에서 프로젝트 {project_id} ({content_type.value}) 조회 중...")

    # ProjectType에 따라 적절한 메서드 호출
    if project_type in [ProjectType.FUNDING_AND_PREORDER, ProjectType.FUNDING, ProjectType.PREORDER]:
        content_items = await es_service.get_funding_preorder_project_contents(
            project_id=project_id,
            content_type=content_type
        )
    else:
        # STORE, GENERAL 등은 별도 구현 필요
        content_items = []

    print(f"   - {len(content_items)}건 조회 완료")
    return content_items


# ============================================================
# 기간 기반 테스트 데이터 셋 생성
# ============================================================

async def _generate_test_dataset_from_period(
    start_date: str,
    end_date: str,
    max_items_per_project: Optional[int] = None
) -> List[MultiProjectTestItem]:
    """
    특정 기간 동안 생성된 데이터를 기반으로 테스트 데이터 셋 생성.

    모든 ExternalContentType에 대해 조회 후 { project_id, project_type, content_type } 단위로 그룹핑.
    body 필드를 함께 조회하여 content_items를 pre-load합니다.

    Args:
        start_date: 시작 일시 (UTC, ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)
                    예시: "2026-02-24T15:00:00" (KST 2026-02-25T00:00:00)
        end_date: 종료 일시 (UTC, ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)
                  예시: "2026-03-04T14:59:59" (KST 2026-03-04T23:59:59)
        max_items_per_project: 프로젝트당 최대 아이템 수 (None이면 제한 없음)

    Returns:
        List[MultiProjectTestItem]: 테스트 대상 프로젝트 리스트 (content_items 포함)

    Note:
        각 provider 테스트에서 _convert_kst_to_utc()를 사용하여 KST→UTC 변환 후 전달하세요.

    Examples:
        # KST 시간을 UTC로 변환하여 전달
        start_utc = _convert_kst_to_utc("2026-02-25T00:00:00")  # KST
        end_utc = _convert_kst_to_utc("2026-03-04T23:59:59")    # KST
        await _generate_test_dataset_from_period(
            start_date=start_utc,
            end_date=end_utc,
            max_items_per_project=50
        )
    """
    from collections import defaultdict
    from src.core.elasticsearch_config import es_manager

    print(f"\n{'='*80}")
    print(f"기간 기반 테스트 데이터 셋 생성")
    print(f"{'='*80}")
    print(f"기간 (UTC): {start_date} ~ {end_date}")
    print(f"프로젝트당 최대 아이템: {max_items_per_project or '제한 없음'}")

    es_client = es_manager.reference_client
    test_items: List[MultiProjectTestItem] = []

    # 모든 ExternalContentType에 대해 조회
    for content_type in ExternalContentType:
        internal_types = content_type.to_internal()
        index_pattern = internal_types[0].index_pattern

        print(f"\n>>> {content_type.value} 조회 중 (인덱스: {index_pattern})")

        # groupsubcode 조건 생성
        if internal_types[0].uses_groupsubcode:
            groupsubcodes = [t.name for t in internal_types]
            content_filter = {"terms": {"groupsubcode.keyword": groupsubcodes}}
        else:
            content_filter = None

        # ES 쿼리: body 포함 조회
        must_conditions = [
            {
                "range": {
                    "createdat": {  # ES 필드명: createdat (언더스코어 없음)
                        "gte": start_date,
                        "lte": end_date
                    }
                }
            }
        ]
        if content_filter:
            must_conditions.append(content_filter)

        search_query = {
            "query": {
                "bool": {
                    "must": must_conditions
                }
            },
            "size": 10000,  # 최대 10000건 조회
            "sort": [{"seq": {"order": "asc"}}],
            "_source": ["seq", "body", "campaignid", "groupsubcode"]
        }

        try:
            response = es_client.search(index=index_pattern, body=search_query)
            hits = response["hits"]["hits"]

            print(f"   - 조회된 문서: {len(hits)}건")

            # 프로젝트별로 그룹핑
            project_contents: Dict[int, List[ContentItem]] = defaultdict(list)

            for hit in hits:
                source = hit["_source"]
                seq_val = source.get("seq")
                if seq_val is None:
                    continue

                content_id = int(seq_val)
                content_text = source.get("body", "")
                campaign_id = source.get("campaignid")
                groupsubcode = source.get("groupsubcode", "")

                # 빈 콘텐츠 제외
                if not content_text or not content_text.strip():
                    continue

                # campaign_id를 int로 변환
                try:
                    project_id = int(campaign_id)
                except (ValueError, TypeError):
                    continue

                content_item = ContentItem(
                    content_id=content_id,
                    content=content_text.strip(),
                    has_image=(groupsubcode == "PHOTO_REVIEW")
                )
                project_contents[project_id].append(content_item)

            # 프로젝트별 테스트 아이템 생성
            for project_id, contents in project_contents.items():
                # max_items_per_project 적용
                if max_items_per_project:
                    contents = contents[:max_items_per_project]

                # 최소 1개 이상의 콘텐츠가 있는 프로젝트만
                if not contents:
                    continue

                test_items.append(MultiProjectTestItem(
                    project_id=project_id,
                    project_type=ProjectType.FUNDING_AND_PREORDER,  # 기본값 (펀딩/프리오더)
                    content_type=content_type,
                    content_items=contents
                ))

            print(f"   - 생성된 프로젝트: {len(project_contents)}개")

        except Exception as e:
            print(f"   ⚠️ 조회 실패: {e}")
            continue

    print(f"\n총 테스트 대상 프로젝트: {len(test_items)}개")
    return test_items


async def _load_project_content_items_with_limit(
    project_id: int,
    project_type: ProjectType,
    content_type: ExternalContentType,
    max_items: Optional[int] = None
) -> List[ContentItem]:
    """
    ES에서 프로젝트 콘텐츠 로드 (최대 개수 제한 지원)

    Args:
        project_id: 프로젝트 ID
        project_type: 프로젝트 타입
        content_type: 콘텐츠 타입
        max_items: 최대 아이템 수 (None이면 제한 없음)

    Returns:
        List[ContentItem]: 콘텐츠 아이템 리스트
    """
    content_items = await _load_project_content_items(project_id, project_type, content_type)

    if max_items and len(content_items) > max_items:
        content_items = content_items[:max_items]
        print(f"   - {max_items}개로 슬라이스됨")

    return content_items


# ============================================================
# Multi-Project 청킹 시뮬레이션
# ============================================================

async def _run_multi_project_chunking_simulation(
    provider_name: str,
    test_input: MultiProjectTestInput,
    output_base_dir: str
) -> MultiProjectTestOutput:
    """
    Multi-Project 순차 청킹 시뮬레이션

    Args:
        provider_name: Provider 이름 (출력 경로용)
        test_input: 테스트 입력 (프로젝트 배열, chunk_size, max_chunks)
        output_base_dir: 출력 기본 경로 (datetime 디렉터리)

    Returns:
        MultiProjectTestOutput: 테스트 결과
    """
    print(f"\n{'='*80}")
    print(f"Multi-Project 순차 청킹 시뮬레이션")
    print(f"{'='*80}")
    print(f"Provider: {provider_name}")
    print(f"프로젝트 수: {len(test_input.projects)}")
    print(f"청크 크기: {test_input.chunk_size}")
    print(f"최대 청크: {test_input.max_chunks or '전체'}")
    print(f"프로젝트당 최대 콘텐츠: {test_input.max_items_per_project or '전체'}")

    # ============================================================
    # 1. 초기화: 프로젝트별 데이터 로드 및 청크 분할
    # ============================================================
    print(f"\n>>> [Step 0] 프로젝트 데이터 로드 및 청크 분할")

    project_states: List[ProjectChunkingState] = []

    for item in test_input.projects:
        # pre-loaded content_items가 있으면 사용, 없으면 ES에서 조회
        if item.content_items:
            content_items = item.content_items
            print(f"   - 프로젝트 {item.project_id}: pre-loaded {len(content_items)}건 사용")
        else:
            content_items = await _load_project_content_items_with_limit(
                item.project_id,
                item.project_type,
                item.content_type,
                max_items=test_input.max_items_per_project
            )

        if not content_items:
            print(f"   ⚠️ 프로젝트 {item.project_id}: 데이터 없음, 건너뜀")
            continue

        chunks = _split_chunks(content_items, test_input.chunk_size)

        state = ProjectChunkingState(
            project_id=item.project_id,
            project_type=item.project_type,
            content_type=item.content_type,
            all_content_items=content_items,
            all_chunks=chunks
        )
        project_states.append(state)

        print(f"   ✅ 프로젝트 {item.project_id}: {len(content_items)}건 → {len(chunks)}청크")

    if not project_states:
        pytest.skip("로드된 프로젝트 데이터가 없습니다.")

    # ============================================================
    # 2. LLM Service 초기화
    # ============================================================
    prompt_manager = PromptManager()
    llm_service = LLMService(prompt_manager)
    all_llm_usages: List[LLMUsageInfo] = []

    # ============================================================
    # 3. 청크 순회 (Step 1: Structuring)
    # ============================================================
    chunk_idx = 0
    max_chunks = test_input.max_chunks

    while True:
        # 활성 프로젝트 필터링 (남은 청크가 있는 프로젝트만)
        active_states = [s for s in project_states if s.has_remaining_chunks()]

        if not active_states:
            print(f"\n>>> 모든 프로젝트 처리 완료")
            break

        if max_chunks is not None and chunk_idx >= max_chunks:
            print(f"\n>>> 최대 청크 수({max_chunks}) 도달, 중단")
            break

        chunk_idx += 1
        print(f"\n>>> [Step 1 - 청크 {chunk_idx}] 활성 프로젝트: {len(active_states)}개")

        # 현재 청크의 배치 구성
        batch: List[MultiProjectBatchItem] = []
        for state in active_states:
            chunk_items = state.get_current_chunk()
            analysis_items = _convert_to_analysis_items(chunk_items)

            batch_item = MultiProjectBatchItem(
                project=state.project_id,
                project_type=state.project_type.value,
                content_type=state.content_type.value,
                content_items=analysis_items,
                previous_result=state.accumulated_result
            )
            batch.append(batch_item)

            has_prev = "있음" if state.accumulated_result else "없음"
            print(f"   - 프로젝트 {state.project_id}: {len(chunk_items)}건, 이전결과: {has_prev}")

        # Multi-Project LLM 호출
        print(f"   🔄 Multi-Project LLM 호출 중...")
        results, usage = await llm_service.multi_project_structure_analysis(batch)
        all_llm_usages = merge_llm_usage_lists(all_llm_usages, [usage])

        print(f"   ✅ 토큰: {usage.input_tokens} / {usage.output_tokens}")

        # 결과 업데이트 및 청크 진행
        results_map = {r.project: r.result for r in results.results}
        for state in active_states:
            if state.project_id in results_map:
                state.accumulated_result = results_map[state.project_id]
                state.advance_chunk()

                remaining = len(state.all_chunks) - state.current_chunk_idx
                if remaining == 0:
                    print(f"   🏁 프로젝트 {state.project_id}: 완료 (다음 청크에서 제외)")

    # ============================================================
    # 4. Refinement (Step 2)
    # ============================================================
    print(f"\n>>> [Step 2] 요약 정제 (Refinement)")

    summary_items: List[MultiProjectSummaryItem] = []
    for state in project_states:
        if state.accumulated_result:
            summary_items.append(MultiProjectSummaryItem(
                project=state.project_id,
                project_type=state.project_type.value,
                content_type=state.content_type.value,
                analysis_data=_to_summary(state.accumulated_result)
            ))

    print(f"   - 정제 대상: {len(summary_items)}개 프로젝트")

    refined_results, refine_usage = await llm_service.multi_project_refine_analysis(
        projects=summary_items,
        persona_type=PersonaType.CUSTOMER_FACING_SMART_BOT
    )
    all_llm_usages = merge_llm_usage_lists(all_llm_usages, [refine_usage])

    print(f"   ✅ 토큰: {refine_usage.input_tokens} / {refine_usage.output_tokens}")

    # ============================================================
    # 5. 최종 결과 병합 (Step 1 + Step 2)
    # ============================================================
    print(f"\n>>> [Step 3] 최종 결과 병합")

    refined_map = {r.project: r.result for r in refined_results.results}
    final_results: Dict[int, StructuredAnalysisResult] = {}

    for state in project_states:
        if state.accumulated_result:
            final_result = state.accumulated_result.model_copy(deep=True)

            # Step 2 정제 결과 적용
            if state.project_id in refined_map:
                refined = refined_map[state.project_id]
                final_result.summary = refined.summary
                final_result.keywords = refined.keywords
                final_result.good_points = refined.good_points
                final_result.caution_points = refined.caution_points

                # 카테고리별 정제 요약 적용
                refined_cat_map = {c.key: c for c in refined.categories}
                for cat in final_result.categories:
                    if cat.key in refined_cat_map:
                        cat.summary = refined_cat_map[cat.key].summary
                        cat.keywords = refined_cat_map[cat.key].keywords

            final_results[state.project_id] = final_result
            print(f"   ✅ 프로젝트 {state.project_id}: {len(final_result.categories)}개 카테고리")

    # ============================================================
    # 6. 통계 집계
    # ============================================================
    per_project_stats = [
        {
            "project_id": state.project_id,
            "content_count": state.total_content_count,
            "chunks_used": state.chunks_used
        }
        for state in project_states
    ]

    total_content_items = sum(s.total_content_count for s in project_states)

    output = MultiProjectTestOutput(
        results=final_results,
        llm_usages=all_llm_usages,
        total_chunks_processed=chunk_idx,
        total_content_items=total_content_items,
        per_project_stats=per_project_stats
    )

    # ============================================================
    # 7. 결과 저장 (JSON + HTML)
    # ============================================================
    await _save_results(
        output=output,
        test_input=test_input,
        provider_name=provider_name,
        output_base_dir=output_base_dir
    )

    return output


async def _save_results(
    output: MultiProjectTestOutput,
    test_input: MultiProjectTestInput,
    provider_name: str,
    output_base_dir: str
):
    """결과 저장 (JSON + HTML)"""
    # Provider별 디렉터리 생성
    provider_dir = os.path.join(output_base_dir, provider_name)
    os.makedirs(provider_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    executed_at = datetime.now().isoformat()

    # 총 소요 시간 계산
    total_duration_ms = sum(u.duration_ms for u in output.llm_usages if u.duration_ms)
    total_duration_formatted = _format_duration(total_duration_ms / 1000)

    # ============================================================
    # JSON 저장
    # ============================================================
    json_path = os.path.join(provider_dir, f"multi_project_{timestamp}.json")

    json_data = {
        "test_input": {
            "projects": [
                {
                    "project_id": p.project_id,
                    "project_type": p.project_type.value,
                    "content_type": p.content_type.value
                }
                for p in test_input.projects
            ],
            "chunk_size": test_input.chunk_size,
            "max_chunks": test_input.max_chunks
        },
        "execution_summary": {
            "provider": provider_name,
            "total_chunks_processed": output.total_chunks_processed,
            "total_content_items": output.total_content_items,
            "total_duration_ms": total_duration_ms,
            "total_duration_formatted": total_duration_formatted,
            "executed_at": executed_at
        },
        "per_project_stats": output.per_project_stats,
        "llm_usages": [u.model_dump() for u in output.llm_usages],
        "results": {
            str(project_id): result.model_dump()
            for project_id, result in output.results.items()
        }
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"\n💾 JSON 저장: {json_path}")

    # ============================================================
    # HTML 저장 (프로젝트별)
    # ============================================================
    for project_id, result in output.results.items():
        html_path = os.path.join(provider_dir, f"multi_project_{project_id}_{timestamp}.html")

        # 해당 프로젝트의 콘텐츠 수 찾기
        project_stat = next((s for s in output.per_project_stats if s["project_id"] == project_id), None)
        total_items = project_stat["content_count"] if project_stat else 0

        html_content = GenerationViewer.generate_detail_html(
            result=result,
            project_id=project_id,
            total_items=total_items,
            executed_at=executed_at,
            total_duration=total_duration_formatted,
            content_type_description="Multi-Project 배치 분석",
            provider_name=provider_name,
            llm_usages=output.llm_usages
        )

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"🌐 HTML 저장: {html_path}")


# ============================================================
# 테스트 실행 함수
# ============================================================

async def _execute_multi_project_test(
    provider_name: str,
    test_input: MultiProjectTestInput
):
    """테스트 실행 공통 로직"""
    # datetime 디렉터리 생성
    current_dir = os.path.dirname(__file__)
    datetime_dir = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_base_dir = os.path.join(current_dir, "..", "data", "multi_project", datetime_dir)
    os.makedirs(output_base_dir, exist_ok=True)

    output = await _run_multi_project_chunking_simulation(
        provider_name=provider_name,
        test_input=test_input,
        output_base_dir=output_base_dir
    )

    # 검증
    assert output is not None
    assert len(output.results) > 0, "최소 1개 이상의 프로젝트 결과가 있어야 합니다"
    assert len(output.llm_usages) > 0, "LLM 사용량 정보가 있어야 합니다"

    # 프로젝트 완전성 검증
    input_project_ids = {p.project_id for p in test_input.projects}
    output_project_ids = set(output.results.keys())
    # 데이터가 없는 프로젝트는 제외될 수 있으므로 subset 검증
    assert output_project_ids.issubset(input_project_ids), "출력 프로젝트는 입력의 부분집합이어야 합니다"

    print(f"\n{'='*80}")
    print(f"✅ 테스트 완료")
    print(f"   - 처리된 프로젝트: {len(output.results)}개")
    print(f"   - 총 청크: {output.total_chunks_processed}개")
    print(f"   - 총 콘텐츠: {output.total_content_items}건")
    print(f"{'='*80}")


# ============================================================
# 테스트 데이터
# ============================================================

DEFAULT_TEST_PROJECTS = [
    MultiProjectTestItem(
        project_id=365330,
        project_type=ProjectType.FUNDING_AND_PREORDER,
        content_type=ExternalContentType.REVIEW
    ),
    MultiProjectTestItem(
        project_id=324284,
        project_type=ProjectType.FUNDING_AND_PREORDER,
        content_type=ExternalContentType.REVIEW
    ),
    MultiProjectTestItem(
        project_id=309305,
        project_type=ProjectType.FUNDING_AND_PREORDER,
        content_type=ExternalContentType.SATISFACTION
    ),
]

DEFAULT_TEST_INPUT = MultiProjectTestInput(
    projects=DEFAULT_TEST_PROJECTS,
    chunk_size=50,
    max_chunks=3  # 테스트 시간 단축용
)


# ============================================================
# Provider별 테스트
# ============================================================

@pytest.mark.asyncio
async def test_multi_project_simulation(setup_elasticsearch):
    """기본 Provider로 Multi-Project 청킹 시뮬레이션 테스트"""
    provider_name = settings.llm_provider.value.lower()
    await _execute_multi_project_test(
        provider_name=provider_name,
        test_input=DEFAULT_TEST_INPUT
    )


@pytest.mark.asyncio
async def test_vertexai_multi_project_simulation(setup_elasticsearch):
    """Vertex AI Provider Multi-Project 테스트"""
    with switch_llm_provider(ProviderType.VERTEX_AI):
        await _execute_multi_project_test(
            provider_name="vertex_ai",
            test_input=DEFAULT_TEST_INPUT
        )


@pytest.mark.asyncio
async def test_gemini_api_multi_project_simulation(setup_elasticsearch):
    """Gemini API Provider Multi-Project 테스트"""
    if not settings.gemini_api.API_KEY:
        pytest.skip("GEMINI_API__API_KEY가 설정되지 않았습니다.")

    with switch_llm_provider(ProviderType.GEMINI_API):
        await _execute_multi_project_test(
            provider_name="gemini_api",
            test_input=DEFAULT_TEST_INPUT
        )


@pytest.mark.asyncio
async def test_openai_multi_project_simulation(setup_elasticsearch):
    """OpenAI Provider Multi-Project 테스트"""
    if not settings.openai.API_KEY:
        pytest.skip("OPENAI_API_KEY가 설정되지 않았습니다.")

    with switch_llm_provider(ProviderType.OPENAI):
        await _execute_multi_project_test(
            provider_name="openai",
            test_input=DEFAULT_TEST_INPUT
        )


# ============================================================
# 기간 기반 테스트 데이터 셋 Provider별 테스트
# ============================================================

# 테스트 기간 설정 (KST 기준)
# 형식: ISO 8601 (YYYY-MM-DDTHH:MM:SS)
# 예시:
#   - "2026-03-01T00:00:00" ~ "2026-03-04T23:59:59" (특정 기간)
#   - "2026-03-04T09:00:00" ~ "2026-03-04T18:00:00" (당일 업무 시간)
# 주의: 각 provider 테스트에서 KST→UTC 변환 후 전달 필요
PERIOD_TEST_MAX_ITEMS = 50  # 프로젝트당 최대 50개
PERIOD_TEST_MAX_PROJECTS = 50  # 최대 50개 프로젝트만 테스트


async def _execute_period_based_multi_project_test(
    provider_name: str,
    start_date: str,
    end_date: str,
    max_items_per_project: int = PERIOD_TEST_MAX_ITEMS,
    max_projects: int = PERIOD_TEST_MAX_PROJECTS
):
    """
    기간 기반 테스트 데이터 셋을 사용한 테스트 공통 로직

    Args:
        provider_name: Provider 이름
        start_date: 시작 일시 (UTC, ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)
                    예시: "2026-02-28T15:00:00" (KST 2026-03-01T00:00:00)
        end_date: 종료 일시 (UTC, ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)
                  예시: "2026-03-04T14:59:59" (KST 2026-03-04T23:59:59)
        max_items_per_project: 프로젝트당 최대 콘텐츠 수 (기본값: 50)
        max_projects: 테스트할 최대 프로젝트 수 (기본값: 5)

    Note:
        start_date, end_date는 UTC 기준입니다.
        각 provider 테스트에서 _convert_kst_to_utc()를 사용하여 KST→UTC 변환 후 전달하세요.

    Examples:
        # KST 시간을 UTC로 변환하여 전달
        start_kst = "2026-03-01T00:00:00"
        end_kst = "2026-03-04T23:59:59"
        await _execute_period_based_multi_project_test(
            provider_name="vertex_ai",
            start_date=_convert_kst_to_utc(start_kst),
            end_date=_convert_kst_to_utc(end_kst),
            max_items_per_project=100,
            max_projects=10
        )
    """
    # 1. 테스트 데이터 셋 생성
    test_items = await _generate_test_dataset_from_period(
        start_date=start_date,
        end_date=end_date,
        max_items_per_project=max_items_per_project
    )

    if not test_items:
        pytest.skip(f"기간 {start_date} ~ {end_date}에 테스트 데이터가 없습니다.")

    # 2. 최대 프로젝트 수로 슬라이스
    if len(test_items) > max_projects:
        test_items = test_items[:max_projects]
        print(f"테스트 프로젝트 수를 {max_projects}개로 제한")

    # 3. 테스트 입력 구성
    test_input = MultiProjectTestInput(
        projects=test_items,
        chunk_size=50,
        max_chunks=None,  # 전체 처리
        max_items_per_project=max_items_per_project
    )

    # 4. 테스트 실행
    await _execute_multi_project_test(
        provider_name=provider_name,
        test_input=test_input
    )


@pytest.mark.asyncio
async def test_period_based_multi_project_simulation(setup_elasticsearch):
    """기본 Provider로 기간 기반 Multi-Project 테스트"""
    # KST 기간 설정 (예: 최근 7일)
    start_kst = "2026-02-25T00:00:00"
    end_kst = "2026-03-04T23:59:59"

    provider_name = settings.llm_provider.value.lower()
    await _execute_period_based_multi_project_test(
        provider_name=provider_name,
        start_date=_convert_kst_to_utc(start_kst),
        end_date=_convert_kst_to_utc(end_kst)
    )


@pytest.mark.asyncio
async def test_period_based_vertexai_multi_project_simulation(setup_elasticsearch):
    """Vertex AI Provider 기간 기반 Multi-Project 테스트"""
    # KST 기간 설정 (예: 최근 7일)
    start_kst = "2026-02-25T00:00:00"
    end_kst = "2026-03-04T23:59:59"

    with switch_llm_provider(ProviderType.VERTEX_AI):
        await _execute_period_based_multi_project_test(
            provider_name="vertex_ai",
            start_date=_convert_kst_to_utc(start_kst),
            end_date=_convert_kst_to_utc(end_kst)
        )


@pytest.mark.asyncio
async def test_period_based_gemini_api_multi_project_simulation(setup_elasticsearch):
    """Gemini API Provider 기간 기반 Multi-Project 테스트"""
    if not settings.gemini_api.API_KEY:
        pytest.skip("GEMINI_API__API_KEY가 설정되지 않았습니다.")

    # KST 기간 설정 (예: 최근 7일)
    start_kst = "2026-02-13T09:00:00"
    end_kst = "2026-02-13T13:00:00"

    with switch_llm_provider(ProviderType.GEMINI_API):
        await _execute_period_based_multi_project_test(
            provider_name="gemini_api",
            start_date=_convert_kst_to_utc(start_kst),
            end_date=_convert_kst_to_utc(end_kst)
        )


@pytest.mark.asyncio
async def test_period_based_openai_multi_project_simulation(setup_elasticsearch):
    """OpenAI Provider 기간 기반 Multi-Project 테스트"""
    if not settings.openai.API_KEY:
        pytest.skip("OPENAI_API_KEY가 설정되지 않았습니다.")

    # KST 기간 설정 (예: 최근 7일)
    start_kst = "2026-02-25T00:00:00"
    end_kst = "2026-03-04T23:59:59"

    with switch_llm_provider(ProviderType.OPENAI):
        await _execute_period_based_multi_project_test(
            provider_name="openai",
            start_date=_convert_kst_to_utc(start_kst),
            end_date=_convert_kst_to_utc(end_kst)
        )
