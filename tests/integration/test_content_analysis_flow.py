import json
import os
import random
import time
from datetime import datetime, timedelta

import pytest

from src.core.session_factory import SessionFactory
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.prompt.structured_analysis_summary import CategorySummaryItem, StructuredAnalysisSummary
from src.services.llm_service import LLMService
from src.utils.prompt_manager import PromptManager

# tests/data/test_contents.py에서 정적 데이터 임포트
from tests.data.test_contents import MILD_NEGATIVE_CONTENT, NEGATIVE_CONTENT_QUALITY, POSITIVE_CONTENT, TOXIC_CONTENT


def _format_duration(seconds: float) -> str:
    """
    초 단위 시간을 HH:MM:SS.sss 형태로 변환

    Args:
        seconds: 초 단위 시간

    Returns:
        HH:MM:SS.sss 형식의 문자열
    """
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


async def _execute_content_analysis_flow(project_id: int, sample_contents: list,
                                         project_type: ProjectType = ProjectType.FUNDING_AND_PREORDER,
                                         show_content_details: bool = True,
                                         save_output: bool = False,
                                         output_file_path: str = None
                                         ):
    """
    상세 분석 플로우 공통 실행 로직

    Args:
        project_id: 프로젝트 ID
        sample_contents: 분석할 콘텐츠 리스트 (dict 또는 ContentItem)
        show_content_details: 콘텐츠 상세 내용 출력 여부
        save_output: 결과를 파일로 저장 여부
        output_file_path: 출력 파일 경로

    Returns:
        tuple: (step1_response, step2_response, final_response, total_duration)
    """
    # dict 형식의 데이터를 ContentItem 객체로 변환
    content_items = []
    for item in sample_contents:
        if isinstance(item, dict):
            content_items.append(ContentItem(
                content_id=item.get('id') or item.get('content_id'),
                content=item['content'],
                has_image=item.get('has_image', False)
            ))
        else:
            content_items.append(item)
    # 1. Setup Service
    SessionFactory.initialize()
    prompt_manager = PromptManager()
    llm_service = LLMService(prompt_manager)

    # 2. Display Input Summary
    print(f"\n>>> Total input items: {len(content_items)}")
    if show_content_details:
        for item in content_items:
            img_icon = "📷" if item.has_image else "📝"
            print(f"  - [{item.content_id}] {img_icon} {item.content[:30]}...")
    else:
        # Only show counts and image distribution
        image_count = sum(1 for item in content_items if item.has_image)
        print(f"  - Content items: {len(content_items)}")
        print(f"  - With images: {image_count} 📷")
        print(f"  - Without images: {len(content_items) - image_count} 📝")

    total_start_time = time.time()

    # 3. Step 1: Main Analysis (PRO_DATA_ANALYST)
    print("\n\n>>> [Step 1] Executing Main Analysis (PRO_DATA_ANALYST)...")
    step1_start_time = time.time()
    
    step1_response, _ = await llm_service.structure_content_analysis(
        project_id=project_id,
        project_type=project_type,
        content_items=content_items
    )
    step1_duration = time.time() - step1_start_time
    
    print(f"\n✅ [Step 1 Result] (Duration: {step1_duration:.2f}s)")
    if show_content_details:
        print("=" * 80)
        print(step1_response.model_dump_json(indent=2, ensure_ascii=False))
        print("=" * 80)
    else:
        print(f"  - Categories found: {len(step1_response.categories)}")
        print(f"  - Summary length: {len(step1_response.summary)} chars")

    # 4. Step 2: Refinement with CUSTOMER_FACING_SMART_BOT
    print("\n\n>>> [Step 2] Executing Summary Refinement (CUSTOMER_FACING_SMART_BOT)...")
    step2_start_time = time.time()
    
    # Step1 결과를 StructuredAnalysisSummary로 변환
    refine_content_items = StructuredAnalysisSummary(
        summary=step1_response.summary,
        categories=[
            CategorySummaryItem(key=cat.key, summary=cat.summary)
            for cat in step1_response.categories
        ]
    )
    
    step2_response, _ = await llm_service.refine_analysis_summary(
        project_id=project_id,
        project_type=project_type,
        refine_content_items=refine_content_items,
        persona_type=PersonaType.CUSTOMER_FACING_SMART_BOT
    )
    step2_duration = time.time() - step2_start_time
    
    print(f"\n✅ [Step 2 Result] (Duration: {step2_duration:.2f}s)")
    if show_content_details:
        print("=" * 80)
        print(step2_response.model_dump_json(indent=2, ensure_ascii=False))
        print("=" * 80)
    else:
        print(f"  - Refined summary length: {len(step2_response.summary)} chars")
        print(f"  - Refined categories: {len(step2_response.categories)}")

    # 5. Merge & Print Final Result
    print("\n\n>>> [Final] Merging Step 1 & Step 2 Results...")
    
    # Merge Logic (simulating Orchestrator)
    final_response = step1_response.model_copy(deep=True)
    final_response.summary = step2_response.summary
    
    refined_map = {cat.key: cat.summary for cat in step2_response.categories}
    for category in final_response.categories:
        if category.key in refined_map:
            category.summary = refined_map[category.key]
            
    total_duration = time.time() - total_start_time
    
    print(f"\n✅ [Final Merged Result] (Duration: {total_duration:.2f}s)")
    if show_content_details:
        print("=" * 80)
        print(final_response.model_dump_json(indent=2, ensure_ascii=False))
        print("=" * 80)
    
    print(f"\n🕒 [Total Execution Time]: {total_duration:.2f}s")
    
    # 6. Save output if requested
    if save_output and output_file_path:
        # Add execution time to each result (JSON 문자열을 dict로 파싱)
        step1_result = json.loads(step1_response.model_dump_json())
        step1_result["execution_time_seconds"] = round(step1_duration, 2)
        step1_result["execution_time_formatted"] = _format_duration(step1_duration)

        step2_result = json.loads(step2_response.model_dump_json())
        step2_result["execution_time_seconds"] = round(step2_duration, 2)
        step2_result["execution_time_formatted"] = _format_duration(step2_duration)

        final_result = json.loads(final_response.model_dump_json())
        final_result["execution_time_seconds"] = round(total_duration, 2)
        final_result["execution_time_formatted"] = _format_duration(total_duration)

        output_data = {
            "execution_time": {
                "step1_duration_seconds": round(step1_duration, 2),
                "step1_duration_formatted": _format_duration(step1_duration),
                "step2_duration_seconds": round(step2_duration, 2),
                "step2_duration_formatted": _format_duration(step2_duration),
                "total_duration_seconds": round(total_duration, 2),
                "total_duration_formatted": _format_duration(total_duration),
                "executed_at": datetime.now().isoformat()
            },
            "input_summary": {
                "total_items": len(content_items),
                "items_with_image": sum(1 for item in content_items if item.has_image),
                "project_id": project_id,
                "project_type": project_type.value
            },
            "step1_result": step1_result,
            "step2_result": step2_result,
            "final_result": final_result
        }

        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 [Output Saved]: {output_file_path}")
    
    return step1_response, step2_response, final_response, total_duration


@pytest.mark.asyncio
async def test_llm_service_content_analysis_flow_static():
    """
    LLMService 상세 분석 통합 테스트 - 정적 데이터
    - 데이터 소스: tests/data/test_contents.py (정적 변수, has_image 포함)
    - 정제 페르소나: CUSTOMER_FACING_SMART_BOT
    - 결과: 전체 데이터 출력 및 단계별 소요 시간 측정
    """
    # Prepare Data with has_image field
    sample_contents = [
        {"id": 101, "content": POSITIVE_CONTENT, "has_image": True},
        {"id": 102, "content": NEGATIVE_CONTENT_QUALITY, "has_image": False},
        {"id": 103, "content": MILD_NEGATIVE_CONTENT, "has_image": True},
        {"id": 104, "content": TOXIC_CONTENT, "has_image": False},
    ]

    project_id = 88888

    try:
        step1_response, step2_response, final_response, total_duration = await _execute_content_analysis_flow(
            project_id=project_id, sample_contents=sample_contents, show_content_details=True)
        
        assert step1_response is not None
        assert len(step1_response.categories) > 0
        assert step2_response is not None
        assert len(step2_response.summary) > 0
        
    except Exception as e:
        pytest.fail(f"Static data analysis flow failed: {e}")


@pytest.mark.asyncio
async def test_llm_service_content_analysis_flow_project_file():
    """
    LLMService 상세 분석 통합 테스트 - 프로젝트 파일 데이터
    - 데이터 소스: tests/data/project_365330.json (JSON 파일)
    - 정제 페르소나: CUSTOMER_FACING_SMART_BOT
    - 결과: 요약 정보만 출력, 전체 결과는 파일로 저장
    """
    # Load project data from JSON file
    current_dir = os.path.dirname(__file__)
    project_file_path = os.path.join(current_dir, "..", "data", "project_365330.json")
    
    if not os.path.exists(project_file_path):
        pytest.skip(f"Project data file not found: {project_file_path}")
    
    try:
        with open(project_file_path, 'r', encoding='utf-8') as f:
            content_items = json.load(f)
    except Exception as e:
        pytest.fail(f"Failed to load project data: {e}")
    
    # Validate data structure
    if not isinstance(content_items, list):
        pytest.fail("Project data should be a JSON array")
    
    if len(content_items) == 0:
        pytest.skip("No content items in project data file")
    
    project_id = 365330
    
    # Prepare output file path
    output_file_path = os.path.join(
        os.path.dirname(project_file_path), 
        f"project_365330_analysis_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    is_all = False
    # Sample items for testing (랜덤 또는 순차 선택)
    sample_size = 500

    if not is_all:
        use_random_sampling = True  # True: 랜덤 샘플링, False: 앞에서부터 순차 선택
        if use_random_sampling:
            random.shuffle(content_items)
            print(f"\n📊 Shuffled and sampled {min(sample_size, len(content_items))} items from {len(content_items)} total items")

    test_content_items = content_items if is_all else content_items[:sample_size]

    try:
        step1_response, step2_response, final_response, total_duration = await _execute_content_analysis_flow(
            project_id=project_id, sample_contents=test_content_items, show_content_details=False, save_output=True,
            output_file_path=output_file_path)
        
        assert step1_response is not None
        assert len(step1_response.categories) > 0
        assert step2_response is not None
        assert len(step2_response.summary) > 0
        assert os.path.exists(output_file_path), "Output file should be created"
        
    except Exception as e:
        pytest.fail(f"Project file analysis flow failed: {e}")


# Legacy test name for backward compatibility
test_llm_service_content_analysis_flow = test_llm_service_content_analysis_flow_static