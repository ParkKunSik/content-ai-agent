import pytest
import time
import json
import os
from datetime import datetime
from src.services.llm_service import LLMService
from src.utils.prompt_manager import PromptManager
from src.core.model_factory import ModelFactory
from src.schemas.enums.persona_type import PersonaType

# tests/data/test_contents.py에서 정적 데이터 임포트
from tests.data.test_contents import (
    POSITIVE_CONTENT,
    NEGATIVE_CONTENT_QUALITY,
    MILD_NEGATIVE_CONTENT,
    TOXIC_CONTENT
)


async def _execute_detailed_analysis_flow(project_id: int, sample_contents: list, 
                                        show_content_details: bool = True, 
                                        save_output: bool = False, 
                                        output_file_path: str = None):
    """
    상세 분석 플로우 공통 실행 로직
    
    Args:
        project_id: 프로젝트 ID
        sample_contents: 분석할 콘텐츠 리스트
        show_content_details: 콘텐츠 상세 내용 출력 여부
        save_output: 결과를 파일로 저장 여부
        output_file_path: 출력 파일 경로
    
    Returns:
        tuple: (step1_response, step2_response, final_response, total_duration)
    """
    # 1. Setup Service
    ModelFactory.initialize()
    prompt_manager = PromptManager()
    llm_service = LLMService(prompt_manager)

    # 2. Display Input Summary
    print(f"\n>>> Total input items: {len(sample_contents)}")
    if show_content_details:
        for item in sample_contents:
            img_icon = "📷" if item.get('has_image', False) else "📝"
            print(f"  - [{item['content_id']}] {img_icon} {item['content'][:30]}...")
    else:
        # Only show counts and image distribution
        image_count = sum(1 for item in sample_contents if item.get('has_image', False))
        print(f"  - Content items: {len(sample_contents)}")
        print(f"  - With images: {image_count} 📷")
        print(f"  - Without images: {len(sample_contents) - image_count} 📝")

    total_start_time = time.time()

    # 3. Step 1: Main Analysis (PRO_DATA_ANALYST)
    print(f"\n\n>>> [Step 1] Executing Main Analysis (PRO_DATA_ANALYST)...")
    step1_start_time = time.time()
    
    step1_response = await llm_service.perform_detailed_analysis(
        project_id=project_id,
        content_items=sample_contents
    )
    step1_duration = time.time() - step1_start_time
    
    print(f"\n✅ [Step 1 Result] (Duration: {step1_duration:.2f}s)")
    if show_content_details:
        print("=" * 80)
        print(step1_response.model_dump_json(indent=2, ensure_ascii=False))
        print("=" * 80)
    else:
        print(f"  - Categories found: {len(step1_response.categorys)}")
        print(f"  - Summary length: {len(step1_response.summary)} chars")

    # 4. Step 2: Refinement with CUSTOMER_FACING_SMART_BOT
    print(f"\n\n>>> [Step 2] Executing Summary Refinement (CUSTOMER_FACING_SMART_BOT)...")
    step2_start_time = time.time()
    
    step2_response = await llm_service.refine_analysis_summary(
        project_id=project_id,
        raw_analysis_data=step1_response.model_dump_json(),
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
        print(f"  - Refined categories: {len(step2_response.categorys)}")

    # 5. Merge & Print Final Result
    print(f"\n\n>>> [Final] Merging Step 1 & Step 2 Results...")
    
    # Merge Logic (simulating Orchestrator)
    final_response = step1_response.model_copy(deep=True)
    final_response.summary = step2_response.summary
    
    refined_map = {cat.category_key: cat.summary for cat in step2_response.categorys}
    for category in final_response.categorys:
        if category.category_key in refined_map:
            category.summary = refined_map[category.category_key]
            
    total_duration = time.time() - total_start_time
    
    print(f"\n✅ [Final Merged Result] (Duration: {total_duration:.2f}s)")
    if show_content_details:
        print("=" * 80)
        print(final_response.model_dump_json(indent=2, ensure_ascii=False))
        print("=" * 80)
    
    print(f"\n🕒 [Total Execution Time]: {total_duration:.2f}s")
    
    # 6. Save output if requested
    if save_output and output_file_path:
        output_data = {
            "execution_time": {
                "step1_duration": step1_duration,
                "step2_duration": step2_duration,
                "total_duration": total_duration,
                "executed_at": datetime.now().isoformat()
            },
            "input_summary": {
                "total_items": len(sample_contents),
                "items_with_image": sum(1 for item in sample_contents if item.get('has_image', False)),
                "project_id": project_id
            },
            "step1_result": step1_response.model_dump(),
            "step2_result": step2_response.model_dump(),
            "final_result": final_response.model_dump()
        }
        
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 [Output Saved]: {output_file_path}")
    
    return step1_response, step2_response, final_response, total_duration


@pytest.mark.asyncio
async def test_llm_service_detailed_analysis_flow_static():
    """
    LLMService 상세 분석 통합 테스트 - 정적 데이터
    - 데이터 소스: tests/data/test_contents.py (정적 변수, has_image 포함)
    - 정제 페르소나: CUSTOMER_FACING_SMART_BOT
    - 결과: 전체 데이터 출력 및 단계별 소요 시간 측정
    """
    # Prepare Data with has_image field
    sample_contents = [
        {"content_id": 101, "content": POSITIVE_CONTENT, "has_image": True},
        {"content_id": 102, "content": NEGATIVE_CONTENT_QUALITY, "has_image": False},
        {"content_id": 103, "content": MILD_NEGATIVE_CONTENT, "has_image": True},
        {"content_id": 104, "content": TOXIC_CONTENT, "has_image": False},
    ]

    project_id = 88888

    try:
        step1_response, step2_response, final_response, total_duration = await _execute_detailed_analysis_flow(
            project_id=project_id,
            sample_contents=sample_contents,
            show_content_details=True  # Show full content for static test
        )
        
        assert step1_response is not None
        assert len(step1_response.categorys) > 0
        assert step2_response is not None
        assert len(step2_response.summary) > 0
        
    except Exception as e:
        pytest.fail(f"Static data analysis flow failed: {e}")


@pytest.mark.asyncio
async def test_llm_service_detailed_analysis_flow_project_file():
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
    
    # Ensure has_image field exists (default to False if not present)
    for item in content_items:
        if 'has_image' not in item:
            item['has_image'] = False
    
    project_id = 365330
    
    # Prepare output file path
    output_file_path = os.path.join(
        os.path.dirname(project_file_path), 
        f"project_365330_analysis_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    try:
        step1_response, step2_response, final_response, total_duration = await _execute_detailed_analysis_flow(
            project_id=project_id,
            sample_contents=content_items,
            show_content_details=False,  # Only show summary for large datasets
            save_output=True,
            output_file_path=output_file_path
        )
        
        assert step1_response is not None
        assert len(step1_response.categorys) > 0
        assert step2_response is not None
        assert len(step2_response.summary) > 0
        assert os.path.exists(output_file_path), "Output file should be created"
        
    except Exception as e:
        pytest.fail(f"Project file analysis flow failed: {e}")


# Legacy test name for backward compatibility
test_llm_service_detailed_analysis_flow = test_llm_service_detailed_analysis_flow_static