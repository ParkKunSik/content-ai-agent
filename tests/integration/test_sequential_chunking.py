"""
순차 청킹 기능 통합 테스트 (LLM 통합 방식)

테스트 시나리오:
1. 이전 버전 없이 신규 분석
2. 이전 버전 있을 때 기존 결과 + 새 콘텐츠 통합 분석
3. LLMUsageInfo 합산 검증
4. Provider별 테스트 (Vertex AI, Gemini API, OpenAI)
5. 순차 청킹 시뮬레이션 (N등분 → 반복 실행)
"""
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Optional

import pytest

from src.core.config.settings import settings
from src.core.llm.enums import ProviderType
from src.core.llm.registry import ProviderRegistry
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.common.llm_usage_info import LLMUsageInfo
from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult
from src.schemas.models.prompt.structured_analysis_summary import CategorySummaryItem, StructuredAnalysisSummary
from src.services.es_content_retrieval_service import ESContentRetrievalService
from src.services.llm_service import LLMService
from src.utils.generation_viewer import GenerationViewer
from src.utils.llm_usage_aggregator import merge_llm_usage_lists, merge_llm_usages
from src.utils.prompt_manager import PromptManager


def _format_duration(seconds: float) -> str:
    """초 단위 시간을 HH:MM:SS.sss 형태로 변환"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


# ============================================================
# Helper: Provider 전환 Context Manager
# ============================================================

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


# ============================================================
# Helper: 테스트 데이터 로드 (ES에서 조회)
# ============================================================

async def _load_test_content_items_from_es(
    project_id: int,
    content_type: ExternalContentType
) -> List[ContentItem]:
    """ES에서 테스트용 ContentItem 리스트 조회"""
    es_service = ESContentRetrievalService()

    print(f"\n>>> ES에서 프로젝트 {project_id}, 타입 {content_type.value} 조회 중...")
    content_items = await es_service.get_funding_preorder_project_contents(
        project_id=project_id,
        content_type=content_type
    )

    if not content_items:
        pytest.skip(f"ES에서 프로젝트 {project_id}의 {content_type.value} 콘텐츠를 찾을 수 없습니다.")

    print(f">>> ES에서 {len(content_items)}개 콘텐츠 조회 완료")
    return content_items


# ============================================================
# Unit Tests: LLMUsageInfo 합산
# ============================================================

class TestLLMUsageAggregator:
    """LLMUsageInfo 합산 로직 테스트"""

    def test_merge_single_usage_to_empty_list(self):
        """빈 리스트에 단일 사용량 추가"""
        existing: List[LLMUsageInfo] = []
        new_usage = LLMUsageInfo(
            step=1,
            model="gemini-2.0-flash-001",
            input_tokens=1000,
            output_tokens=500,
            duration_ms=1500,
            input_cost=0.001,
            output_cost=0.002,
            total_cost=0.003
        )

        result = merge_llm_usages(existing, new_usage)

        assert len(result) == 1
        assert result[0].step == 1
        assert result[0].input_tokens == 1000
        assert result[0].output_tokens == 500

    def test_merge_same_step_and_model(self):
        """동일한 step과 model일 때 합산"""
        existing = [
            LLMUsageInfo(
                step=1, model="gemini-2.5-flash",
                input_tokens=1000, output_tokens=500, duration_ms=2000,
                input_cost=0.0001, output_cost=0.0002, total_cost=0.0003
            )
        ]
        new_usage = LLMUsageInfo(
            step=1, model="gemini-2.5-flash",
            input_tokens=800, output_tokens=400, duration_ms=1500,
            input_cost=0.00008, output_cost=0.00016, total_cost=0.00024
        )

        result = merge_llm_usages(existing, new_usage)

        assert len(result) == 1
        assert result[0].input_tokens == 1800
        assert result[0].output_tokens == 900
        assert result[0].duration_ms == 3500

    def test_merge_different_step(self):
        """다른 step일 때 리스트에 추가"""
        existing = [
            LLMUsageInfo(step=1, model="gemini-2.5-flash", input_tokens=1000, output_tokens=500, duration_ms=2000)
        ]
        new_usage = LLMUsageInfo(step=2, model="gemini-2.5-flash", input_tokens=500, output_tokens=300, duration_ms=1000)

        result = merge_llm_usages(existing, new_usage)

        assert len(result) == 2
        assert result[0].step == 1
        assert result[1].step == 2

    def test_merge_different_model(self):
        """다른 model일 때 리스트에 추가"""
        existing = [
            LLMUsageInfo(step=1, model="gemini-2.5-flash", input_tokens=1000, output_tokens=500, duration_ms=2000)
        ]
        new_usage = LLMUsageInfo(step=1, model="gpt-4o", input_tokens=500, output_tokens=300, duration_ms=1000)

        result = merge_llm_usages(existing, new_usage)

        assert len(result) == 2

    def test_merge_lists(self):
        """두 리스트 병합"""
        existing = [
            LLMUsageInfo(step=1, model="gemini-2.5-flash", input_tokens=1000, output_tokens=500, duration_ms=2000)
        ]
        new_usages = [
            LLMUsageInfo(step=1, model="gemini-2.5-flash", input_tokens=500, output_tokens=200, duration_ms=1000),
            LLMUsageInfo(step=2, model="gemini-2.5-flash", input_tokens=300, output_tokens=150, duration_ms=800)
        ]

        result = merge_llm_usage_lists(existing, new_usages)

        assert len(result) == 2
        assert result[0].input_tokens == 1500  # step=1 합산
        assert result[1].step == 2

    def test_merge_with_none_costs(self):
        """cost가 None인 경우 안전하게 합산"""
        existing = [
            LLMUsageInfo(
                step=1,
                model="gemini-2.0-flash-001",
                input_tokens=1000,
                output_tokens=500,
                duration_ms=1500,
                input_cost=None,
                output_cost=None,
                total_cost=None
            )
        ]
        new_usage = LLMUsageInfo(
            step=1,
            model="gemini-2.0-flash-001",
            input_tokens=500,
            output_tokens=250,
            duration_ms=750,
            input_cost=0.001,
            output_cost=0.002,
            total_cost=0.003
        )

        result = merge_llm_usages(existing, new_usage)

        assert len(result) == 1
        assert result[0].input_tokens == 1500
        assert result[0].total_cost == pytest.approx(0.003)


# ============================================================
# Integration Tests: 순차 청킹 시뮬레이션 (LLM 통합 방식)
# ============================================================

async def _run_sequential_chunking_simulation(
    provider_name: str,
    project_id: int,
    content_type: ExternalContentType,
    chunk_size: int = 100,
    max_chunks: Optional[int] = None
):
    """
    순차 청킹 시뮬레이션 실행 (LLM 통합 방식)

    전체 데이터를 N등분하여 순차적으로 분석하고,
    각 단계에서 이전 결과(StructuredAnalysisResult 전체)를 LLM에 전달하여 통합합니다.
    최종 결과에 대해 Step 2 Refinement를 수행합니다.

    Args:
        provider_name: Provider 이름 (출력 경로용)
        project_id: 프로젝트 ID
        content_type: 콘텐츠 타입
        chunk_size: 청크당 콘텐츠 수
        max_chunks: 최대 청크 수 (None이면 전체 순회)
    """
    # ES에서 데이터 조회
    all_contents = await _load_test_content_items_from_es(project_id, content_type)

    # 청크 분할
    chunks = [all_contents[i:i+chunk_size] for i in range(0, len(all_contents), chunk_size)]

    # max_chunks가 None이면 전체 순회, 아니면 제한
    if max_chunks is not None:
        chunks = chunks[:max_chunks]

    print(f"\n📊 순차 청킹 시뮬레이션 시작 (LLM 통합 방식)")
    print(f"   - Provider: {provider_name}")
    print(f"   - 전체 데이터: {len(all_contents)}건")
    print(f"   - 청크 크기: {chunk_size}건")
    print(f"   - 청크 수: {len(chunks)}개" + (" (전체)" if max_chunks is None else f" (최대 {max_chunks}개)"))

    prompt_manager = PromptManager()
    llm_service = LLMService(prompt_manager)

    previous_result: Optional[StructuredAnalysisResult] = None
    all_llm_usages: List[LLMUsageInfo] = []
    step1_result: Optional[StructuredAnalysisResult] = None

    # ============================================================
    # Step 1: 순차 청킹 분석 (Main Analysis)
    # ============================================================
    for i, chunk in enumerate(chunks):
        print(f"\n>>> [Step 1 - 청크 {i+1}/{len(chunks)}] {len(chunk)}건 분석 중...")

        if previous_result:
            print(f"    - 기존 결과: {len(previous_result.categories)}개 카테고리")

        # LLM 호출: 기존 결과 전체 + 새 콘텐츠 → 통합된 결과 출력
        result, usage = await llm_service.structure_content_analysis(
            project_id=project_id,
            project_type=ProjectType.FUNDING_AND_PREORDER,
            content_items=chunk,
            content_type=content_type,
            previous_result=previous_result  # 기존 결과 전체 전달
        )

        print(f"    - 통합 결과: {len(result.categories)}개 카테고리")
        print(f"    - 토큰: {usage.input_tokens} / {usage.output_tokens}")

        # 다음 청크를 위해 현재 결과 저장 (LLM이 통합한 전체 결과)
        previous_result = result
        all_llm_usages = merge_llm_usage_lists(all_llm_usages, [usage])
        step1_result = result

    # ============================================================
    # Step 2: Refinement (요약 정제)
    # ============================================================
    print(f"\n>>> [Step 2] 요약 정제 (Refinement) 수행 중...")

    # Step1 결과를 StructuredAnalysisSummary로 변환
    refine_content_items = StructuredAnalysisSummary(
        summary=step1_result.summary,
        keywords=step1_result.keywords,
        good_points=step1_result.good_points,
        caution_points=step1_result.caution_points,
        categories=[
            CategorySummaryItem(key=cat.key, summary=cat.summary, keywords=cat.keywords)
            for cat in step1_result.categories
        ]
    )

    # Step 2 Refinement 수행
    refinement_result, refine_usage = await llm_service.refine_analysis_summary(
        project_id=project_id,
        project_type=ProjectType.FUNDING_AND_PREORDER,
        refine_content_items=refine_content_items,
        persona_type=PersonaType.CUSTOMER_FACING_SMART_BOT,
        content_type=content_type
    )
    all_llm_usages = merge_llm_usage_lists(all_llm_usages, [refine_usage])

    print(f"    - 정제된 요약 길이: {len(refinement_result.summary)}자")
    print(f"    - 토큰: {refine_usage.input_tokens} / {refine_usage.output_tokens}")

    # ============================================================
    # Step 3: 최종 결과 병합 (Step1 + Step2)
    # ============================================================
    print(f"\n>>> [Step 3] 최종 결과 병합 중...")

    # Step1 결과를 복사하고 Step2의 정제된 요약으로 대체
    final_result = step1_result.model_copy(deep=True)
    final_result.summary = refinement_result.summary
    final_result.keywords = refinement_result.keywords
    final_result.good_points = refinement_result.good_points
    final_result.caution_points = refinement_result.caution_points

    # 카테고리별 정제된 요약/키워드 적용
    refined_map = {
        cat.key: {"summary": cat.summary, "keywords": cat.keywords}
        for cat in refinement_result.categories
    }
    for category in final_result.categories:
        if category.key in refined_map:
            category.summary = refined_map[category.key]["summary"]
            category.keywords = refined_map[category.key]["keywords"]

    print(f"    - 최종 카테고리 수: {len(final_result.categories)}개")

    # ============================================================
    # 결과 저장 (JSON + HTML)
    # ============================================================
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    executed_at = datetime.now().isoformat()
    current_dir = os.path.dirname(__file__)
    output_dir = os.path.join(current_dir, "..", "data", "chunking", provider_name)
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, f"sequential_chunking_{project_id}_{timestamp}.json")
    html_path = os.path.join(output_dir, f"sequential_chunking_{project_id}_{timestamp}.html")

    # 최종 결과에서 content_id 통계
    total_content_ids = set()
    if final_result:
        for cat in final_result.categories:
            total_content_ids.update(c.id for c in cat.positive_contents)
            total_content_ids.update(c.id for c in cat.negative_contents)
        total_content_ids.update(final_result.harmful_contents)
        total_content_ids.update(e.id for e in final_result.etc_contents)

    # 총 소요 시간 계산
    total_duration_ms = sum(u.duration_ms for u in all_llm_usages if u.duration_ms)
    total_duration_formatted = _format_duration(total_duration_ms / 1000)
    total_input_items = sum(len(chunk) for chunk in chunks)

    output_data = {
        "project_id": project_id,
        "provider": provider_name,
        "content_type": content_type.value,
        "chunks_processed": len(chunks),
        "total_input_items": total_input_items,
        "total_content_ids_in_result": len(total_content_ids),
        "llm_usages": [u.model_dump() for u in all_llm_usages],
        "step1_result": step1_result.model_dump() if step1_result else None,
        "step2_result": refinement_result.model_dump() if refinement_result else None,
        "final_result": final_result.model_dump() if final_result else None
    }

    # JSON 저장
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 JSON 저장: {json_path}")

    # HTML 생성 및 저장 (상세 뷰어 스타일 - LLM 사용량 포함)
    if final_result:
        html_content = GenerationViewer.generate_detail_html(
            result=final_result,
            project_id=project_id,
            total_items=total_input_items,
            executed_at=executed_at,
            total_duration=total_duration_formatted,
            content_type_description=f"고객 의견({content_type.description})",
            provider_name=provider_name,
            llm_usages=all_llm_usages
        )
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"🌐 HTML 저장: {html_path}")

    print(f"📈 총 LLMUsageInfo: {len(all_llm_usages)}개")
    print(f"📊 최종 결과 content_ids: {len(total_content_ids)}개")

    return final_result, all_llm_usages


@pytest.mark.asyncio
async def test_sequential_chunking_simulation(setup_elasticsearch):
    """기본 Provider로 순차 청킹 시뮬레이션 테스트"""
    provider_name = settings.llm_provider.value.lower()
    result, usages = await _run_sequential_chunking_simulation(
        provider_name=provider_name
        , project_id=365330
        , content_type=ExternalContentType.REVIEW
        , chunk_size=100
        # , max_chunks=3
    )

    assert result is not None
    assert len(result.categories) > 0
    assert len(usages) > 0


@pytest.mark.asyncio
async def test_vertexai_sequential_chunking_simulation(setup_elasticsearch):
    """Vertex AI Provider 순차 청킹 시뮬레이션 테스트"""
    with switch_llm_provider(ProviderType.VERTEX_AI):
        result, usages = await _run_sequential_chunking_simulation(
            provider_name="vertex_ai"
            , project_id=324284
            , content_type=ExternalContentType.REVIEW
            , chunk_size=100
            , max_chunks=3
        )

        assert result is not None


@pytest.mark.asyncio
async def test_gemini_api_sequential_chunking_simulation(setup_elasticsearch):
    """Gemini API Provider 순차 청킹 시뮬레이션 테스트"""
    if not settings.gemini_api.API_KEY:
        pytest.skip("GEMINI_API__API_KEY가 설정되지 않았습니다.")

    with switch_llm_provider(ProviderType.GEMINI_API):
        result, usages = await _run_sequential_chunking_simulation(
            provider_name="gemini_api"
            , project_id=313767
            , content_type=ExternalContentType.SUGGESTION
            , chunk_size=100
            , max_chunks=3
        )

        assert result is not None


@pytest.mark.asyncio
async def test_openai_sequential_chunking_simulation(setup_elasticsearch):
    """OpenAI Provider 순차 청킹 시뮬레이션 테스트"""
    if not settings.openai.API_KEY:
        pytest.skip("OPENAI_API_KEY가 설정되지 않았습니다.")

    with switch_llm_provider(ProviderType.OPENAI):
        result, usages = await _run_sequential_chunking_simulation(
            provider_name="openai"
            , project_id=324284
            , content_type=ExternalContentType.REVIEW
            , chunk_size=100
            , max_chunks=3
        )

        assert result is not None
