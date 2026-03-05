"""
개별 프로젝트 병렬 호출 통합 테스트

Multi-Project 배치 방식과 비교하기 위한 개별 프로젝트 병렬 호출 테스트.
동일한 테스트 데이터를 사용하여 토큰/비용 비교 분석 가능.

테스트 시나리오:
1. LLMService.parallel_project_structure_analysis 사용
2. LLMService.parallel_project_refine_analysis 사용
3. Provider별 테스트 (Vertex AI, Gemini API, OpenAI)
4. 결과 출력 (JSON + HTML)

비교 문서: documents/multi-project-cost-comparison-analysis.md
"""
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
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
from src.services.llm_service import LLMService
from src.utils.generation_viewer import GenerationViewer
from src.utils.llm_usage_aggregator import merge_llm_usage_lists
from src.utils.prompt_manager import PromptManager


# ============================================================
# 설정
# ============================================================

# 동시 실행 수 (Rate Limit 고려)
# - 안전: 5개
# - 균형 (권장): 10개
# - 공격적: 20개
CONCURRENT_LIMIT = 10


# ============================================================
# 테스트 데이터 구조
# ============================================================

@dataclass
class MultiProjectTestItem:
    """테스트 대상 단일 프로젝트"""
    project_id: int
    project_type: ProjectType
    content_type: ExternalContentType
    content_items: Optional[List[ContentItem]] = None  # pre-loaded 콘텐츠


@dataclass
class MultiProjectTestInput:
    """테스트 입력 전체"""
    projects: List[MultiProjectTestItem]
    chunk_size: int = 100
    max_chunks: Optional[int] = None
    max_items_per_project: Optional[int] = None


@dataclass
class ParallelProjectTestOutput:
    """테스트 출력"""
    results: Dict[int, StructuredAnalysisResult]
    llm_usages: List[LLMUsageInfo]  # 전체 합산 (요약 표시용)
    project_llm_usages: Dict[int, List[LLMUsageInfo]]  # 프로젝트별 사용량
    total_content_items: int
    per_project_stats: List[dict]
    concurrent_limit: int  # 동시 실행 수 기록
    wall_clock_duration_ms: int  # 실제 경과 시간 (병렬 실행 고려)


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

    Returns:
        UTC 일시 문자열 (ISO 8601 형식)
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


def _convert_to_analysis_items(content_items: List[ContentItem]) -> List[AnalysisContentItem]:
    """ContentItem 리스트를 AnalysisContentItem 리스트로 변환"""
    return [
        AnalysisContentItem(
            id=item.content_id,
            content=item.content,
            has_image=item.has_image if item.has_image is True else None
        )
        for item in content_items
    ]


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
    (test_multi_project_chunking.py와 동일한 로직)
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

    for content_type in ExternalContentType:
        internal_types = content_type.to_internal()
        index_pattern = internal_types[0].index_pattern

        print(f"\n>>> {content_type.value} 조회 중 (인덱스: {index_pattern})")

        if internal_types[0].uses_groupsubcode:
            groupsubcodes = [t.name for t in internal_types]
            content_filter = {"terms": {"groupsubcode.keyword": groupsubcodes}}
        else:
            content_filter = None

        must_conditions = [
            {
                "range": {
                    "createdat": {
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
            "size": 10000,
            "sort": [{"seq": {"order": "asc"}}],
            "_source": ["seq", "body", "campaignid", "groupsubcode"]
        }

        try:
            response = es_client.search(index=index_pattern, body=search_query)
            hits = response["hits"]["hits"]

            print(f"   - 조회된 문서: {len(hits)}건")

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

                if not content_text or not content_text.strip():
                    continue

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

            for project_id, contents in project_contents.items():
                if max_items_per_project:
                    contents = contents[:max_items_per_project]

                if not contents:
                    continue

                test_items.append(MultiProjectTestItem(
                    project_id=project_id,
                    project_type=ProjectType.FUNDING_AND_PREORDER,
                    content_type=content_type,
                    content_items=contents
                ))

            print(f"   - 생성된 프로젝트: {len(project_contents)}개")

        except Exception as e:
            print(f"   ⚠️ 조회 실패: {e}")
            continue

    print(f"\n총 테스트 대상 프로젝트: {len(test_items)}개")
    return test_items


# ============================================================
# 개별 프로젝트 병렬 처리 (LLMService 사용)
# ============================================================

async def _run_parallel_project_simulation(
    provider_name: str,
    test_input: MultiProjectTestInput,
    output_base_dir: str,
    concurrent_limit: int = CONCURRENT_LIMIT
) -> ParallelProjectTestOutput:
    """
    개별 프로젝트 병렬 호출 시뮬레이션 (LLMService.parallel_* 메서드 사용)

    Args:
        provider_name: Provider 이름 (출력 경로용)
        test_input: 테스트 입력
        output_base_dir: 출력 기본 경로
        concurrent_limit: 동시 실행 제한 수

    Returns:
        ParallelProjectTestOutput: 테스트 결과
    """
    print(f"\n{'='*80}")
    print(f"개별 프로젝트 병렬 호출 시뮬레이션 (LLMService.parallel_* 사용)")
    print(f"{'='*80}")
    print(f"Provider: {provider_name}")
    print(f"프로젝트 수: {len(test_input.projects)}")
    print(f"동시 실행 수: {concurrent_limit}")

    # LLMService 초기화
    prompt_manager = PromptManager()
    llm_service = LLMService(prompt_manager)

    # ============================================================
    # 1. 초기화: 프로젝트 데이터를 MultiProjectBatchItem으로 변환
    # ============================================================
    print(f"\n>>> [Step 0] 프로젝트 데이터 준비")

    batch_items: List[MultiProjectBatchItem] = []
    project_content_counts: Dict[int, int] = {}

    for item in test_input.projects:
        if not item.content_items:
            print(f"   ⚠️ 프로젝트 {item.project_id}: content_items 없음, 건너뜀")
            continue

        # ContentItem → AnalysisContentItem 변환
        analysis_items = _convert_to_analysis_items(item.content_items)

        batch_item = MultiProjectBatchItem(
            project=item.project_id,
            project_type=item.project_type.value,
            content_type=item.content_type.value,
            content_items=analysis_items,
            previous_result=None
        )
        batch_items.append(batch_item)
        project_content_counts[item.project_id] = len(item.content_items)

        print(f"   ✅ 프로젝트 {item.project_id}: {len(analysis_items)}건")

    if not batch_items:
        pytest.skip("로드된 프로젝트 데이터가 없습니다.")

    # ============================================================
    # 2. Step 1: 병렬 구조화 분석 (LLMService.parallel_project_structure_analysis)
    # ============================================================
    print(f"\n>>> [Step 1] 병렬 구조화 분석 ({len(batch_items)}개 프로젝트, max_workers={concurrent_limit})")

    wall_clock_start = time.time()

    step1_result, step1_usages = await llm_service.parallel_project_structure_analysis(
        projects=batch_items,
        max_workers=concurrent_limit
    )

    step1_duration_ms = int((time.time() - wall_clock_start) * 1000)
    print(f"   ⏱️ Step 1 완료: {_format_duration(step1_duration_ms / 1000)}")

    # Step 1 결과와 사용량을 프로젝트별로 매핑 (results와 usages는 동일 순서)
    project_llm_usages: Dict[int, List[LLMUsageInfo]] = {}
    for result_item, usage in zip(step1_result.results, step1_usages):
        project_id = result_item.project
        if project_id not in project_llm_usages:
            project_llm_usages[project_id] = []
        project_llm_usages[project_id].append(usage)

    # ============================================================
    # 3. Step 2: 병렬 요약 정제 (LLMService.parallel_project_refine_analysis)
    # ============================================================
    print(f"\n>>> [Step 2] 병렬 요약 정제")

    # Step 1 결과를 MultiProjectSummaryItem으로 변환
    summary_items: List[MultiProjectSummaryItem] = []

    for result_item in step1_result.results:
        summary_data = _to_summary(result_item.result)
        summary_item = MultiProjectSummaryItem(
            project=result_item.project,
            project_type=result_item.project_type,
            content_type=result_item.content_type,
            analysis_data=summary_data
        )
        summary_items.append(summary_item)

    step2_start = time.time()

    step2_result, step2_usages = await llm_service.parallel_project_refine_analysis(
        projects=summary_items,
        persona_type=PersonaType.CUSTOMER_FACING_SMART_BOT,
        max_workers=concurrent_limit
    )

    step2_duration_ms = int((time.time() - step2_start) * 1000)
    print(f"   ⏱️ Step 2 완료: {_format_duration(step2_duration_ms / 1000)}")

    # Step 2 결과와 사용량을 프로젝트별로 매핑
    for result_item, usage in zip(step2_result.results, step2_usages):
        project_id = result_item.project
        if project_id not in project_llm_usages:
            project_llm_usages[project_id] = []
        project_llm_usages[project_id].append(usage)

    wall_clock_end = time.time()
    wall_clock_duration_ms = int((wall_clock_end - wall_clock_start) * 1000)

    # ============================================================
    # 4. 결과 병합 (Step 1 + Step 2)
    # ============================================================
    print(f"\n>>> [결과 병합]")

    # Step 2 결과를 project별로 매핑
    refined_map = {r.project: r.result for r in step2_result.results}

    final_results: Dict[int, StructuredAnalysisResult] = {}
    per_project_stats: List[dict] = []

    for result_item in step1_result.results:
        project_id = result_item.project
        structured_result = result_item.result

        # Step 2 정제 결과 적용
        if project_id in refined_map:
            refined = refined_map[project_id]
            structured_result.summary = refined.summary
            structured_result.keywords = refined.keywords
            structured_result.good_points = refined.good_points
            structured_result.caution_points = refined.caution_points

            # 카테고리별 정제 결과 적용
            refined_cat_map = {c.key: c for c in refined.categories}
            for cat in structured_result.categories:
                if cat.key in refined_cat_map:
                    cat.summary = refined_cat_map[cat.key].summary
                    cat.keywords = refined_cat_map[cat.key].keywords

        final_results[project_id] = structured_result

        # 프로젝트별 통계
        content_count = project_content_counts.get(project_id, 0)
        per_project_stats.append({
            "project_id": project_id,
            "content_count": content_count,
            "categories_count": len(structured_result.categories)
        })

        print(f"   ✅ 프로젝트 {project_id}: {len(structured_result.categories)}개 카테고리")

    # ============================================================
    # 5. LLM 사용량 합산
    # ============================================================
    all_llm_usages = merge_llm_usage_lists(step1_usages, step2_usages)

    total_content_items = sum(project_content_counts.values())

    output = ParallelProjectTestOutput(
        results=final_results,
        llm_usages=all_llm_usages,
        project_llm_usages=project_llm_usages,  # 프로젝트별 사용량
        total_content_items=total_content_items,
        per_project_stats=per_project_stats,
        concurrent_limit=concurrent_limit,
        wall_clock_duration_ms=wall_clock_duration_ms
    )

    # ============================================================
    # 6. 결과 저장 (JSON + HTML)
    # ============================================================
    await _save_results(
        output=output,
        test_input=test_input,
        provider_name=provider_name,
        output_base_dir=output_base_dir
    )

    return output


async def _save_results(
    output: ParallelProjectTestOutput,
    test_input: MultiProjectTestInput,
    provider_name: str,
    output_base_dir: str
):
    """결과 저장 (JSON + HTML)"""
    provider_dir = os.path.join(output_base_dir, provider_name)
    os.makedirs(provider_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    executed_at = datetime.now().isoformat()

    # 실제 경과 시간 (wall-clock) - 병렬 실행 고려
    wall_clock_duration_ms = output.wall_clock_duration_ms
    wall_clock_formatted = _format_duration(wall_clock_duration_ms / 1000)

    # LLM 호출 시간 합계 (선형 합산 - 참고용)
    llm_total_duration_ms = sum(u.duration_ms for u in output.llm_usages if u.duration_ms)
    llm_total_formatted = _format_duration(llm_total_duration_ms / 1000)

    # ============================================================
    # JSON 저장
    # ============================================================
    json_path = os.path.join(provider_dir, f"parallel_project_{timestamp}.json")

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
            "mode": "parallel_individual_llmservice",
            "concurrent_limit": output.concurrent_limit,
            "total_projects": len(output.results),
            "total_content_items": output.total_content_items,
            "executed_at": executed_at
        },
        "timing": {
            "wall_clock_duration_ms": wall_clock_duration_ms,
            "wall_clock_formatted": wall_clock_formatted,
            "llm_total_duration_ms": llm_total_duration_ms,
            "llm_total_formatted": llm_total_formatted,
            "parallelism_efficiency": round(llm_total_duration_ms / wall_clock_duration_ms, 2) if wall_clock_duration_ms > 0 else 0
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
    # 통계 HTML 저장
    # ============================================================
    stats_html_path = os.path.join(provider_dir, f"parallel_project_statistics_{timestamp}.html")

    stats_html = GenerationViewer.generate_usage_statistics_html(
        llm_usages=output.llm_usages,
        title="개별 프로젝트 병렬 호출 - LLM 사용량 통계",
        provider_name=provider_name,
        executed_at=executed_at,
        wall_clock_duration_ms=wall_clock_duration_ms,
        concurrent_limit=output.concurrent_limit,
        total_projects=len(output.results),
        total_content_items=output.total_content_items,
        per_project_stats=output.per_project_stats
    )

    with open(stats_html_path, 'w', encoding='utf-8') as f:
        f.write(stats_html)

    print(f"📊 통계 HTML 저장: {stats_html_path}")

    # ============================================================
    # HTML 저장 (프로젝트별)
    # ============================================================
    wall_clock_formatted_short = _format_duration(wall_clock_duration_ms / 1000)

    for project_id, result in output.results.items():
        html_path = os.path.join(provider_dir, f"parallel_project_{project_id}_{timestamp}.html")

        project_stat = next((s for s in output.per_project_stats if s["project_id"] == project_id), None)
        total_items = project_stat["content_count"] if project_stat else 0

        # 해당 프로젝트의 LLM 사용량만 전달
        project_usages = output.project_llm_usages.get(project_id, [])

        html_content = GenerationViewer.generate_detail_html(
            result=result,
            project_id=project_id,
            total_items=total_items,
            executed_at=executed_at,
            total_duration=wall_clock_formatted_short,
            content_type_description="개별 프로젝트 병렬 호출 (LLMService)",
            provider_name=provider_name,
            llm_usages=project_usages
        )

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"🌐 HTML 저장: {html_path}")


# ============================================================
# 테스트 실행 함수
# ============================================================

async def _execute_parallel_project_test(
    provider_name: str,
    test_input: MultiProjectTestInput,
    concurrent_limit: int = CONCURRENT_LIMIT
):
    """테스트 실행 공통 로직"""
    current_dir = os.path.dirname(__file__)
    datetime_dir = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_base_dir = os.path.join(current_dir, "..", "data", "parallel_project", datetime_dir)
    os.makedirs(output_base_dir, exist_ok=True)

    output = await _run_parallel_project_simulation(
        provider_name=provider_name,
        test_input=test_input,
        output_base_dir=output_base_dir,
        concurrent_limit=concurrent_limit
    )

    # 검증
    assert output is not None
    assert len(output.results) > 0, "최소 1개 이상의 프로젝트 결과가 있어야 합니다"
    assert len(output.llm_usages) > 0, "LLM 사용량 정보가 있어야 합니다"

    # 비용 요약 출력
    total_input_tokens = sum(u.input_tokens for u in output.llm_usages)
    total_output_tokens = sum(u.output_tokens for u in output.llm_usages)
    total_thinking_tokens = sum(u.thinking_tokens for u in output.llm_usages if u.thinking_tokens)
    total_cost = sum(u.total_cost for u in output.llm_usages if u.total_cost)
    llm_total_duration_ms = sum(u.duration_ms for u in output.llm_usages if u.duration_ms)

    print(f"\n{'='*80}")
    print(f"✅ 테스트 완료 (LLMService.parallel_* 사용)")
    print(f"   - 처리된 프로젝트: {len(output.results)}개")
    print(f"   - 총 콘텐츠: {output.total_content_items}건")
    print(f"   - 동시 실행 수: {output.concurrent_limit}개")
    print(f"{'='*80}")
    print(f"⏱️ 시간 요약")
    print(f"   - Wall-Clock 시간: {_format_duration(output.wall_clock_duration_ms / 1000)}")
    print(f"   - LLM 호출 합계: {_format_duration(llm_total_duration_ms / 1000)} (선형 합산)")
    parallelism_efficiency = llm_total_duration_ms / output.wall_clock_duration_ms if output.wall_clock_duration_ms > 0 else 0
    print(f"   - 병렬 효율: {parallelism_efficiency:.1f}x")
    print(f"{'='*80}")
    print(f"📊 토큰/비용 요약")
    print(f"   - Input Tokens: {total_input_tokens:,}")
    print(f"   - Output Tokens: {total_output_tokens:,}")
    if total_thinking_tokens > 0:
        print(f"   - Thinking Tokens: {total_thinking_tokens:,}")
    print(f"   - Total Cost: ${total_cost:.4f}")
    print(f"{'='*80}")


# ============================================================
# 기간 기반 테스트 실행
# ============================================================

PERIOD_TEST_MAX_ITEMS = 50
PERIOD_TEST_MAX_PROJECTS = 50


async def _execute_period_based_parallel_test(
    provider_name: str,
    start_date: str,
    end_date: str,
    max_items_per_project: int = PERIOD_TEST_MAX_ITEMS,
    max_projects: int = PERIOD_TEST_MAX_PROJECTS,
    concurrent_limit: int = CONCURRENT_LIMIT
):
    """
    기간 기반 테스트 데이터 셋을 사용한 병렬 테스트 공통 로직

    Args:
        provider_name: Provider 이름
        start_date: 시작 일시 (UTC)
        end_date: 종료 일시 (UTC)
        max_items_per_project: 프로젝트당 최대 콘텐츠 수
        max_projects: 테스트할 최대 프로젝트 수
        concurrent_limit: 동시 실행 제한 수
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
        max_chunks=None,
        max_items_per_project=max_items_per_project
    )

    # 4. 테스트 실행
    await _execute_parallel_project_test(
        provider_name=provider_name,
        test_input=test_input,
        concurrent_limit=concurrent_limit
    )


# ============================================================
# Provider별 테스트
# ============================================================

@pytest.mark.asyncio
async def test_period_based_parallel_simulation(setup_elasticsearch):
    """기본 Provider로 기간 기반 개별 프로젝트 병렬 테스트"""
    # KST 기간 설정
    start_kst = "2026-02-25T00:00:00"
    end_kst = "2026-03-04T23:59:59"

    provider_name = settings.llm_provider.value.lower()
    await _execute_period_based_parallel_test(
        provider_name=provider_name,
        start_date=_convert_kst_to_utc(start_kst),
        end_date=_convert_kst_to_utc(end_kst)
    )


@pytest.mark.asyncio
async def test_period_based_vertexai_parallel_simulation(setup_elasticsearch):
    """Vertex AI Provider 기간 기반 개별 프로젝트 병렬 테스트"""
    # KST 기간 설정
    start_kst = "2026-02-25T00:00:00"
    end_kst = "2026-03-04T23:59:59"

    with switch_llm_provider(ProviderType.VERTEX_AI):
        await _execute_period_based_parallel_test(
            provider_name="vertex_ai",
            start_date=_convert_kst_to_utc(start_kst),
            end_date=_convert_kst_to_utc(end_kst)
        )


@pytest.mark.asyncio
async def test_period_based_gemini_api_parallel_simulation(setup_elasticsearch):
    """Gemini API Provider 기간 기반 개별 프로젝트 병렬 테스트"""
    if not settings.gemini_api.API_KEY:
        pytest.skip("GEMINI_API__API_KEY가 설정되지 않았습니다.")

    # KST 기간 설정 (Multi-Project 테스트와 동일한 기간 사용)
    start_kst = "2026-02-13T09:00:00"
    end_kst = "2026-02-13T13:00:00"

    with switch_llm_provider(ProviderType.GEMINI_API):
        await _execute_period_based_parallel_test(
            provider_name="gemini_api",
            start_date=_convert_kst_to_utc(start_kst),
            end_date=_convert_kst_to_utc(end_kst)
        )


@pytest.mark.asyncio
async def test_period_based_openai_parallel_simulation(setup_elasticsearch):
    """OpenAI Provider 기간 기반 개별 프로젝트 병렬 테스트"""
    if not settings.openai.API_KEY:
        pytest.skip("OPENAI_API_KEY가 설정되지 않았습니다.")

    # KST 기간 설정
    start_kst = "2026-02-25T00:00:00"
    end_kst = "2026-03-04T23:59:59"

    with switch_llm_provider(ProviderType.OPENAI):
        await _execute_period_based_parallel_test(
            provider_name="openai",
            start_date=_convert_kst_to_utc(start_kst),
            end_date=_convert_kst_to_utc(end_kst)
        )


# ============================================================
# 동시 실행 수 비교 테스트 (선택적)
# ============================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("concurrent_limit", [5, 10, 20])
async def test_concurrent_limit_comparison(setup_elasticsearch, concurrent_limit):
    """
    동시 실행 수에 따른 성능 비교 테스트

    이 테스트는 동일한 데이터셋으로 다양한 concurrent_limit을 테스트합니다.
    결과 JSON에서 total_duration_ms를 비교하여 최적의 동시 실행 수를 확인할 수 있습니다.
    """
    if not settings.gemini_api.API_KEY:
        pytest.skip("GEMINI_API__API_KEY가 설정되지 않았습니다.")

    # 작은 데이터셋으로 테스트
    start_kst = "2026-02-13T09:00:00"
    end_kst = "2026-02-13T10:00:00"  # 1시간 범위

    with switch_llm_provider(ProviderType.GEMINI_API):
        await _execute_period_based_parallel_test(
            provider_name=f"gemini_api_concurrent_{concurrent_limit}",
            start_date=_convert_kst_to_utc(start_kst),
            end_date=_convert_kst_to_utc(end_kst),
            max_projects=10,  # 10개 프로젝트만
            concurrent_limit=concurrent_limit
        )
