import json
import os
import random
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List

import pytest

from src.core.config.settings import settings
from src.core.llm.enums import ProviderType
from src.core.llm.registry import ProviderRegistry
from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.prompt.structured_analysis_summary import CategorySummaryItem, StructuredAnalysisSummary
from src.services.es_content_retrieval_service import ESContentRetrievalService
from src.services.llm_service import LLMService
from src.utils.generation_viewer import PDF_AVAILABLE, GenerationViewer
from src.utils.prompt_manager import PromptManager
from src.utils.token_cost_calculator import (
    TOKEN_COST_CURRENCY,
    calculate_token_usage,
    print_token_usage,
    aggregate_token_usage,
)


@contextmanager
def switch_llm_provider(provider: ProviderType):
    """
    LLM Provider를 임시로 변경하는 Context Manager.
    테스트 종료 후 원래 Provider로 복원한다.
    """
    original_provider = settings.llm_provider
    original_initialized = ProviderRegistry._initialized.copy()
    original_current = ProviderRegistry._current_provider
    try:
        settings.llm_provider = provider
        # Provider 변경 시 Registry 초기화 상태 리셋
        ProviderRegistry._initialized = {k: False for k in ProviderRegistry._initialized}
        ProviderRegistry._current_provider = None
        print(f"\n🔄 LLM Provider 변경: {original_provider.value} → {provider.value}")
        yield
    finally:
        settings.llm_provider = original_provider
        ProviderRegistry._initialized = original_initialized
        ProviderRegistry._current_provider = original_current
        print(f"\n🔄 LLM Provider 복원: {provider.value} → {original_provider.value}")


def _format_duration(seconds: float) -> str:
    """
    초 단위 시간을 HH:MM:SS.sss 형태로 변환
    """
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


async def _execute_content_analysis_with_html(
    project_id: int,
    sample_contents: List[ContentItem],
    project_type: ProjectType = ProjectType.FUNDING_AND_PREORDER,
    show_content_details: bool = False,
    save_output: bool = True,
    output_json_path: str = None,
    output_html_path: str = None,
    output_pdf_path: str = None,
    persona_type: PersonaType = None,
    content_type: ExternalContentType = None,
    content_type_description: str = "고객 의견",
    provider_name: str = None
):
    """
    상세 분석 플로우 실행 후 HTML/PDF 생성 유틸리티를 활용

    Args:
        project_id: 프로젝트 ID
        sample_contents: 분석할 ContentItem 리스트
        project_type: 프로젝트 타입
        show_content_details: 콘텐츠 상세 내용 출력 여부
        save_output: 결과를 파일로 저장 여부
        output_json_path: JSON 출력 파일 경로
        output_html_path: HTML 출력 파일 경로
        output_pdf_path: PDF 출력 파일 경로

    Returns:
        tuple: (step1_response, step2_response, final_response, total_duration, html_path, pdf_path)
    """
    # 1. Setup Service (LLMService 생성 시 ProviderRegistry 자동 초기화)
    prompt_manager = PromptManager()
    llm_service = LLMService(prompt_manager)

    # 2. Display Input Summary
    print(f"\n>>> Total input items: {len(sample_contents)}")
    if show_content_details:
        for item in sample_contents:
            img_icon = "📷" if item.has_image else "📝"
            print(f"  - [{item.content_id}] {img_icon} {item.content[:30]}...")
    else:
        image_count = sum(1 for item in sample_contents if item.has_image)
        print(f"  - Content items: {len(sample_contents)}")
        print(f"  - With images: {image_count} 📷")
        print(f"  - Without images: {len(sample_contents) - image_count} 📝")

    total_start_time = time.time()

    # 3. Step 1: Main Analysis
    print("\n\n>>> [Step 1] Executing Main Analysis (PRO_DATA_ANALYST)...")
    step1_start_time = time.time()

    # ContentItem → AnalysisContentItem 변환
    analysis_items = llm_service._convert_to_analysis_items(sample_contents)
    step1_prompt = prompt_manager.get_content_analysis_structuring_prompt(
        project_id=project_id,
        project_type=project_type,
        content_type=content_type.value if content_type else "ALL",
        analysis_content_items=analysis_items
    )
    step1_response, _ = await llm_service.structure_content_analysis(
        project_id=project_id,
        project_type=project_type,
        content_items=sample_contents
    )
    step1_duration = time.time() - step1_start_time
    step1_token_usage = await calculate_token_usage(
        llm_service.count_total_tokens,
        step1_prompt,
        step1_response.model_dump_json(),
        PersonaType.PRO_DATA_ANALYST.get_model_name()
    )

    print(f"\n✅ [Step 1 Result] (Duration: {step1_duration:.2f}s)")
    print(f"  - Categories found: {len(step1_response.categories)}")
    print(f"  - Summary length: {len(step1_response.summary)} chars")
    print_token_usage("Step 1", step1_token_usage)

    # 4. Step 2: Refinement
    print("\n\n>>> [Step 2] Executing Summary Refinement (CUSTOMER_FACING_SMART_BOT)...")
    step2_start_time = time.time()

    # Step1 결과를 StructuredAnalysisSummary로 변환
    # Step1 결과를 StructuredAnalysisSummary로 변환
    refine_content_items = StructuredAnalysisSummary(
        summary=step1_response.summary,
        categories=[
            CategorySummaryItem(key=cat.key, summary=cat.summary)
            for cat in step1_response.categories
        ]
    )
    step2_prompt = prompt_manager.get_content_analysis_summary_refine_prompt(
        project_id=project_id,
        project_type=project_type,
        content_type=content_type.value if content_type else "ALL",
        refine_content_items=refine_content_items
    )
    step2_response, _ = await llm_service.refine_analysis_summary(
        project_id=project_id,
        project_type=project_type,
        refine_content_items=refine_content_items,
        persona_type=persona_type
    )
    step2_duration = time.time() - step2_start_time
    step2_token_usage = await calculate_token_usage(
        llm_service.count_total_tokens,
        step2_prompt,
        step2_response.model_dump_json(),
        PersonaType.CUSTOMER_FACING_SMART_BOT.get_model_name()
    )

    print(f"\n✅ [Step 2 Result] (Duration: {step2_duration:.2f}s)")
    print(f"  - Refined summary length: {len(step2_response.summary)} chars")
    print(f"  - Refined categories: {len(step2_response.categories)}")
    print_token_usage("Step 2", step2_token_usage)

    # 5. Merge Results
    print("\n\n>>> [Final] Merging Step 1 & Step 2 Results...")

    final_response = step1_response.model_copy(deep=True)
    final_response.summary = step2_response.summary

    refined_map = {cat.key: cat.summary for cat in step2_response.categories}
    for category in final_response.categories:
        if category.key in refined_map:
            category.summary = refined_map[category.key]

    total_duration = time.time() - total_start_time
    total_duration_formatted = _format_duration(total_duration)
    executed_at = datetime.now().isoformat()

    print(f"\n✅ [Final Merged Result] (Duration: {total_duration:.2f}s)")
    print(f"\n🕒 [Total Execution Time]: {total_duration:.2f}s")

    # 6. Save Outputs via GenerationViewer
    html_path = None
    pdf_path = None
    
    if save_output:
        # Save JSON (Original logic kept for complete data preservation)
        if output_json_path:
            # Prepare full output data including tokens and execution times
            step1_result = json.loads(step1_response.model_dump_json())
            step1_result["execution_time_seconds"] = round(step1_duration, 2)
            step1_result["execution_time_formatted"] = _format_duration(step1_duration)

            step2_result = json.loads(step2_response.model_dump_json())
            step2_result["execution_time_seconds"] = round(step2_duration, 2)
            step2_result["execution_time_formatted"] = _format_duration(step2_duration)

            final_result = json.loads(final_response.model_dump_json())
            final_result["execution_time_seconds"] = round(total_duration, 2)
            final_result["execution_time_formatted"] = _format_duration(total_duration)

            total_token_usage = aggregate_token_usage(step1_token_usage, step2_token_usage)

            output_data = {
                "execution_time": {
                    "step1_duration_seconds": round(step1_duration, 2),
                    "step1_duration_formatted": _format_duration(step1_duration),
                    "step2_duration_seconds": round(step2_duration, 2),
                    "step2_duration_formatted": _format_duration(step2_duration),
                    "total_duration_seconds": round(total_duration, 2),
                    "total_duration_formatted": total_duration_formatted,
                    "executed_at": executed_at
                },
                "input_summary": {
                    "total_items": len(sample_contents),
                    "items_with_image": sum(1 for item in sample_contents if item.has_image),
                    "project_id": project_id,
                    "project_type": project_type.value
                },
                "token_usage": {
                    "currency": TOKEN_COST_CURRENCY,
                    "step1": step1_token_usage,
                    "step2": step2_token_usage,
                    "total": total_token_usage
                },
                "step1_result": step1_result,
                "step2_result": step2_result,
                "final_result": final_result
            }
            
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 [JSON Saved]: {output_json_path}")

        # Generate HTML (Using GenerationViewer with Pydantic model directly)
        if output_html_path:
            html_content = GenerationViewer.generate_amazon_style_html(
                result=final_response,
                project_id=project_id,
                total_items=len(sample_contents),
                executed_at=executed_at,
                total_duration=total_duration_formatted,
                content_type_description=content_type_description,
                provider_name=provider_name
            )
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            html_path = output_html_path
            print(f"\n🌐 [HTML Saved]: {output_html_path}")

        # Generate PDF (Using GenerationViewer with Pydantic model directly)
        if output_pdf_path:
            print("\n📄 [PDF Generation]: Starting...")
            pdf_html = GenerationViewer.generate_pdf_optimized_html(
                result=final_response,
                project_id=project_id,
                total_items=len(sample_contents),
                executed_at=executed_at,
                total_duration=total_duration_formatted,
                provider_name=provider_name
            )
            if GenerationViewer.generate_pdf_from_html(pdf_html, output_pdf_path):
                pdf_path = output_pdf_path
                print(f"📄 [PDF Saved]: {output_pdf_path}")
            else:
                print("❌ [PDF Failed]: Could not generate PDF")

    return step1_response, step2_response, final_response, total_duration, html_path, pdf_path


async def _execute_html_generation_test(
    project_id: int,
    content_items: List[ContentItem],
    test_name: str,
    persona_type: PersonaType,
    content_type: ExternalContentType,
    content_type_description: str,
    provider_name: str,
    is_all: bool,
    sample_size: int
):
    """
    공통 HTML 생성 테스트 로직

    Args:
        project_id: 프로젝트 ID
        content_items: 분석할 ContentItem 리스트
        test_name: 테스트명 (파일명에 사용)
        persona_type: 페르소나 타입
        content_type: 콘텐츠 타입 (ExternalContentType)
        content_type_description: 콘텐츠 타입 설명 (HTML 제목에 표시)
        provider_name: LLM Provider 이름 (출력 디렉토리 구분용, 기본값: 현재 설정)
    """
    # Validate data structure
    if len(content_items) == 0:
        pytest.skip("No content items provided")

    # Provider 이름 결정 (지정되지 않으면 현재 설정 사용)
    if provider_name is None:
        provider_name = settings.llm_provider.value.lower()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    current_dir = os.path.dirname(__file__)

    # Provider별 디렉토리 생성
    html_dir = os.path.join(current_dir, "..", "data", "html", provider_name)
    os.makedirs(html_dir, exist_ok=True)

    output_json_path = os.path.join(html_dir, f"project_{project_id}_{test_name}_analysis_{timestamp}.json")
    output_html_path = os.path.join(html_dir, f"project_{project_id}_{test_name}_review_{timestamp}.html")
    # pdf 파일 출력이 필요할 경우 사용
    output_pdf_path = None

    # Sample items for testing (랜덤 또는 순차 선택)
    if not is_all:
        use_random_sampling = True  # True: 랜덤 샘플링, False: 앞에서부터 순차 선택
        if use_random_sampling:
            random.shuffle(content_items)
            print(f"\n📊 Shuffled and sampled {min(sample_size, len(content_items))} items from {len(content_items)} total items")

    test_content_items = content_items if is_all else content_items[:sample_size]

    try:
        step1_res, step2_res, final_res, duration, html_p, pdf_p = \
            await _execute_content_analysis_with_html(
                project_id=project_id,
                sample_contents=test_content_items,
                show_content_details=False,
                save_output=True,
                output_json_path=output_json_path,
                output_html_path=output_html_path,
                output_pdf_path=output_pdf_path,
                persona_type=persona_type,
                content_type=content_type,
                content_type_description=content_type_description,
                provider_name=provider_name
            )

        # Assertions
        assert step1_res is not None
        assert len(step1_res.categories) > 0
        assert step2_res is not None
        assert len(step2_res.summary) > 0
        assert final_res is not None
        
        assert os.path.exists(output_json_path), "JSON output file should be created"
        assert os.path.exists(output_html_path), "HTML output file should be created"
        
        if PDF_AVAILABLE and pdf_p:
            assert os.path.exists(pdf_p), "PDF output file should be created"

        print(f"\n✅ {test_name} test completed successfully!")
        print(f"   - JSON: {output_json_path}")
        print(f"   - HTML: {output_html_path}")
        if PDF_AVAILABLE and pdf_p:
            print(f"   - PDF:  {pdf_p}")

    except Exception as e:
        pytest.fail(f"{test_name} test failed: {e}")


def _load_project_file_content_items():
    """프로젝트 파일에서 ContentItem 리스트를 로드한다."""
    current_dir = os.path.dirname(__file__)
    project_file_path = os.path.join(current_dir, "..", "data", "project_365330.json")

    if not os.path.exists(project_file_path):
        pytest.skip(f"Project data file not found: {project_file_path}")

    try:
        with open(project_file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        # JSON dict를 ContentItem 객체로 변환
        return [
            ContentItem(
                content_id=item.get('id', item.get('content_id')),
                content=item['content'],
                has_image=item.get('has_image', False)
            ) for item in raw_data
        ]
    except Exception as e:
        pytest.fail(f"Failed to load project data: {e}")


async def _test_html_generation_from_project_file(
    provider_name: str,
    project_id: int,
    content_type: ExternalContentType,
    is_all: bool,
    sample_size: int
):
    """
    LLMService 상세 분석 후 HTML 생성 테스트 (내부 구현)

    Args:
        provider_name: LLM Provider 이름 (출력 디렉토리 구분용)
        project_id: 프로젝트 ID
        content_type: 콘텐츠 타입
        is_all: 전체 데이터 사용 여부
        sample_size: 샘플 크기
    """
    content_items = _load_project_file_content_items()

    # 공통 테스트 로직 실행
    await _execute_html_generation_test(
        project_id=project_id,
        content_items=content_items,
        test_name="file",
        persona_type=PersonaType.CUSTOMER_FACING_SMART_BOT,
        content_type=content_type,
        content_type_description=f"고객 의견({content_type.description})",
        provider_name=provider_name,
        is_all=is_all,
        sample_size=sample_size
    )


@pytest.mark.asyncio
async def test_html_generation_from_project_file():
    """
    LLMService 상세 분석 후 HTML 생성 테스트 (기본 Provider)
    - 데이터 소스: tests/data/project_365330.json
    - 출력: JSON + HTML (아마존 리뷰 하이라이트 스타일)
    - HTML 출력 경로: tests/data/html/{provider}/
    """
    await _test_html_generation_from_project_file(
        provider_name=settings.llm_provider.value.lower(),
        project_id=365330,
        content_type=ExternalContentType.REVIEW,
        is_all=False,
        sample_size=200
    )


@pytest.mark.asyncio
async def test_vertexai_html_generation_from_project_file():
    """
    Vertex AI Provider를 사용한 프로젝트 파일 기반 HTML 생성 테스트
    - LLM Provider: VERTEX_AI
    - 데이터 소스: tests/data/project_365330.json
    - HTML 출력 경로: tests/data/html/vertex_ai/
    """
    with switch_llm_provider(ProviderType.VERTEX_AI):
        await _test_html_generation_from_project_file(
            provider_name="vertex_ai",
            project_id=365330,
            content_type=ExternalContentType.REVIEW,
            is_all=False,
            sample_size=200
        )


@pytest.mark.asyncio
async def test_openai_html_generation_from_project_file():
    """
    OpenAI Provider를 사용한 프로젝트 파일 기반 HTML 생성 테스트
    - LLM Provider: OPENAI
    - 데이터 소스: tests/data/project_365330.json
    - HTML 출력 경로: tests/data/html/openai/

    Note: OPENAI_API_KEY 환경변수가 설정되어 있어야 합니다.
    """
    if not settings.openai.API_KEY:
        pytest.skip("OPENAI_API_KEY가 설정되지 않았습니다.")

    with switch_llm_provider(ProviderType.OPENAI):
        await _test_html_generation_from_project_file(
            provider_name="openai",
            project_id=365330,
            content_type=ExternalContentType.REVIEW,
            is_all=False,
            sample_size=200
        )


async def _test_html_generation_from_project_ES(
    setup_elasticsearch,
    provider_name: str,
    project_id: int,
    content_type: ExternalContentType,
    is_all: bool,
    sample_size: int
):
    """
    ESContentRetrievalService를 통한 ES 조회 후 HTML 생성 테스트 (내부 구현)

    Args:
        setup_elasticsearch: ES fixture
        provider_name: LLM Provider 이름 (출력 디렉토리 구분용)
        project_id: 프로젝트 ID
        content_type: 콘텐츠 타입
        is_all: 전체 데이터 사용 여부
        sample_size: 샘플 크기
    """
    try:
        # ES 초기화는 setup_elasticsearch fixture에서 처리
        es_service = ESContentRetrievalService()

        print(f"\n>>> ES에서 프로젝트 {project_id}, 타입 {content_type} 조회 중...")
        content_items = await es_service.get_funding_preorder_project_contents(
            project_id=project_id,
            content_type=content_type
        )

        if not content_items:
            pytest.skip(f"ES에서 프로젝트 {project_id}의 {content_type} 콘텐츠를 찾을 수 없습니다.")

        print(f">>> ES에서 {len(content_items)}개 콘텐츠 조회 완료")

        # 공통 테스트 로직 실행
        await _execute_html_generation_test(
            project_id=project_id,
            content_items=content_items,
            test_name="ES",
            persona_type=PersonaType.CUSTOMER_FACING_SMART_BOT,
            content_type=content_type,
            content_type_description=f"고객 의견({content_type.description})",
            provider_name=provider_name,
            is_all=is_all,
            sample_size=sample_size
        )

    except Exception as e:
        pytest.fail(f"ES 조회 테스트 실패: {e}")


@pytest.mark.asyncio
async def test_html_generation_from_project_ES(setup_elasticsearch):
    """
    ESContentRetrievalService를 통한 ES 조회 후 HTML 생성 테스트 (기본 Provider)
    - 데이터 소스: Elasticsearch
    - 출력: JSON + HTML (아마존 리뷰 하이라이트 스타일)
    - HTML 출력 경로: tests/data/html/{provider}/
    """
    await _test_html_generation_from_project_ES(
        setup_elasticsearch,
        provider_name=settings.llm_provider.value.lower(),
        project_id=276504,
        content_type=ExternalContentType.SATISFACTION,
        is_all=False,
        sample_size=200
    )


@pytest.mark.asyncio
async def test_vertexai_html_generation_from_project_ES(setup_elasticsearch):
    """
    Vertex AI Provider를 사용한 ES 조회 후 HTML 생성 테스트
    - LLM Provider: VERTEX_AI
    - 데이터 소스: Elasticsearch
    - HTML 출력 경로: tests/data/html/vertex_ai/
    """
    with switch_llm_provider(ProviderType.VERTEX_AI):
        await _test_html_generation_from_project_ES(
            setup_elasticsearch,
            provider_name="vertex_ai",
            project_id=335362,
            content_type=ExternalContentType.SATISFACTION,
            is_all=False,
            sample_size=100
        )


@pytest.mark.asyncio
async def test_openai_html_generation_from_project_ES(setup_elasticsearch):
    """
    OpenAI Provider를 사용한 ES 조회 후 HTML 생성 테스트
    - LLM Provider: OPENAI
    - 데이터 소스: Elasticsearch
    - HTML 출력 경로: tests/data/html/openai/

    Note: OPENAI_API_KEY 환경변수가 설정되어 있어야 합니다.
    """
    if not settings.openai.API_KEY:
        pytest.skip("OPENAI_API_KEY가 설정되지 않았습니다.")

    with switch_llm_provider(ProviderType.OPENAI):
        await _test_html_generation_from_project_ES(
            setup_elasticsearch,
            provider_name="openai",
            project_id=335362,
            content_type=ExternalContentType.SATISFACTION,
            is_all=False,
            sample_size=100
        )
