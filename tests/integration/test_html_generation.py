import json
import os
import random
import time
from datetime import datetime, timedelta

import pytest

from src.core.config import settings
from src.core.session_factory import SessionFactory
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.services.llm_service import LLMService
from src.utils.prompt_manager import PromptManager
from src.utils.generation_viewer import GenerationViewer, PDF_AVAILABLE

TOKEN_COST_CURRENCY = "USD"
MODEL_PRICING_TABLE = {
    "gemini_2_5_pro": {
        "input_cost_per_million": 1.25,
        "output_cost_per_million": 5.00
    },
    "gemini_2_5_flash": {
        "input_cost_per_million": 0.10,
        "output_cost_per_million": 0.40
    },
    "gemini_3_pro_preview": {
        "input_cost_per_million": 1.50,
        "output_cost_per_million": 6.00
    },
    "gemini_3_flash_preview": {
        "input_cost_per_million": 0.15,
        "output_cost_per_million": 0.60
    }
}

MODEL_ALIASES = {
    "gemini_2_5_pro": ["gemini-2.5-pro", "gemini-2.5-pro-preview", "gemini 2.5 pro"],
    "gemini_2_5_flash": ["gemini-2.5-flash", "gemini-2.5-flash-preview", "gemini 2.5 flash"],
    "gemini_3_pro_preview": ["gemini-3.0-pro-preview", "gemini-3-pro-preview", "gemini 3 pro (preview)", "gemini 3 pro"],
    "gemini_3_flash_preview": ["gemini-3.0-flash-preview", "gemini-3-flash-preview", "gemini 3 flash (preview)", "gemini 3 flash"]
}


def _normalize_model_name(model_name: str) -> str:
    return model_name.lower().replace(".", "").replace("-", " ").strip()


def _resolve_model_pricing(model_name: str) -> dict:
    normalized = _normalize_model_name(model_name)
    for key, aliases in MODEL_ALIASES.items():
        if any(_normalize_model_name(alias) == normalized for alias in aliases):
            return MODEL_PRICING_TABLE[key]
    print(f"  - Token cost: model '{model_name}' not found in pricing table, costs set to 0")
    return {"input_cost_per_million": 0.0, "output_cost_per_million": 0.0}


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


async def _calculate_token_usage(
    llm_service: LLMService,
    prompt: str,
    response_text: str,
    model_name: str
) -> dict:
    """프롬프트/응답 토큰 및 비용 계산 (모델별 단가)."""
    prompt_tokens = await llm_service.count_total_tokens([prompt])
    output_tokens = await llm_service.count_total_tokens([response_text])
    total_tokens = prompt_tokens + output_tokens

    model_costs = _resolve_model_pricing(model_name)

    input_cost_per_million = model_costs["input_cost_per_million"]
    output_cost_per_million = model_costs["output_cost_per_million"]

    input_cost = round((prompt_tokens / 1_000_000) * input_cost_per_million, 6)
    output_cost = round((output_tokens / 1_000_000) * output_cost_per_million, 6)
    total_cost = round(input_cost + output_cost, 6)

    return {
        "model_name": model_name,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "input_cost_per_million": input_cost_per_million,
        "output_cost_per_million": output_cost_per_million,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "currency": TOKEN_COST_CURRENCY
    }


def _print_token_usage(step_label: str, usage: dict) -> None:
    """토큰 사용량/비용 출력."""
    print(f"  - Token usage ({step_label}): input {usage['prompt_tokens']}, output {usage['output_tokens']}, total {usage['total_tokens']}")
    print(
        f"  - Token cost ({usage['currency']}): "
        f"input {usage['input_cost']}, output {usage['output_cost']}, total {usage['total_cost']}"
    )


async def _execute_detailed_analysis_with_html(
    project_id: int,
    sample_contents: list,
    project_type: ProjectType = ProjectType.FUNDING,
    show_content_details: bool = False,
    save_output: bool = True,
    output_json_path: str = None,
    output_html_path: str = None,
    output_pdf_path: str = None
):
    """
    상세 분석 플로우 실행 후 HTML/PDF 생성 유틸리티를 활용

    Args:
        project_id: 프로젝트 ID
        sample_contents: 분석할 콘텐츠 리스트
        project_type: 프로젝트 타입
        show_content_details: 콘텐츠 상세 내용 출력 여부
        save_output: 결과를 파일로 저장 여부
        output_json_path: JSON 출력 파일 경로
        output_html_path: HTML 출력 파일 경로
        output_pdf_path: PDF 출력 파일 경로

    Returns:
        tuple: (step1_response, step2_response, final_response, total_duration, html_path, pdf_path)
    """
    # 1. Setup Service
    SessionFactory.initialize()
    prompt_manager = PromptManager()
    llm_service = LLMService(prompt_manager)

    # 2. Display Input Summary
    print(f"\n>>> Total input items: {len(sample_contents)}")
    if show_content_details:
        for item in sample_contents:
            img_icon = "📷" if item.get('has_image', False) else "📝"
            item_id = item.get('id') or item.get('content_id')
            print(f"  - [{item_id}] {img_icon} {item['content'][:30]}...")
    else:
        image_count = sum(1 for item in sample_contents if item.get('has_image', False))
        print(f"  - Content items: {len(sample_contents)}")
        print(f"  - With images: {image_count} 📷")
        print(f"  - Without images: {len(sample_contents) - image_count} 📝")

    total_start_time = time.time()

    # 3. Step 1: Main Analysis
    print(f"\n\n>>> [Step 1] Executing Main Analysis (PRO_DATA_ANALYST)...")
    step1_start_time = time.time()

    analysis_items = llm_service._convert_to_analysis_items(sample_contents)
    step1_prompt = prompt_manager.get_detailed_analysis_prompt(
        project_id=project_id,
        project_type=project_type,
        content_items=json.dumps(analysis_items, ensure_ascii=False, separators=(',', ':'))
    )
    step1_response = await llm_service.perform_detailed_analysis(
        project_id=project_id,
        project_type=project_type,
        content_items=sample_contents
    )
    step1_duration = time.time() - step1_start_time
    step1_token_usage = await _calculate_token_usage(
        llm_service,
        step1_prompt,
        step1_response.model_dump_json(),
        settings.VERTEX_AI_MODEL_PRO
    )

    print(f"\n✅ [Step 1 Result] (Duration: {step1_duration:.2f}s)")
    print(f"  - Categories found: {len(step1_response.categories)}")
    print(f"  - Summary length: {len(step1_response.summary)} chars")
    _print_token_usage("Step 1", step1_token_usage)

    # 4. Step 2: Refinement
    print(f"\n\n>>> [Step 2] Executing Summary Refinement (CUSTOMER_FACING_SMART_BOT)...")
    step2_start_time = time.time()

    step2_prompt = prompt_manager.get_detailed_analysis_summary_refine_prompt(
        project_id=project_id,
        project_type=project_type,
        raw_analysis_data=step1_response.model_dump_json()
    )
    step2_response = await llm_service.refine_analysis_summary(
        project_id=project_id,
        project_type=project_type,
        raw_analysis_data=step1_response.model_dump_json(),
        persona_type=PersonaType.CUSTOMER_FACING_SMART_BOT
    )
    step2_duration = time.time() - step2_start_time
    step2_token_usage = await _calculate_token_usage(
        llm_service,
        step2_prompt,
        step2_response.model_dump_json(),
        settings.VERTEX_AI_MODEL_FLASH
    )

    print(f"\n✅ [Step 2 Result] (Duration: {step2_duration:.2f}s)")
    print(f"  - Refined summary length: {len(step2_response.summary)} chars")
    print(f"  - Refined categories: {len(step2_response.categories)}")
    _print_token_usage("Step 2", step2_token_usage)

    # 5. Merge Results
    print(f"\n\n>>> [Final] Merging Step 1 & Step 2 Results...")

    final_response = step1_response.model_copy(deep=True)
    final_response.summary = step2_response.summary

    refined_map = {cat.category_key: cat.summary for cat in step2_response.categories}
    for category in final_response.categories:
        if category.category_key in refined_map:
            category.summary = refined_map[category.category_key]

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

            total_token_usage = {
                "model_name": "combined",
                "prompt_tokens": step1_token_usage["prompt_tokens"] + step2_token_usage["prompt_tokens"],
                "output_tokens": step1_token_usage["output_tokens"] + step2_token_usage["output_tokens"],
                "total_tokens": step1_token_usage["total_tokens"] + step2_token_usage["total_tokens"],
                "input_cost": round(step1_token_usage["input_cost"] + step2_token_usage["input_cost"], 6),
                "output_cost": round(step1_token_usage["output_cost"] + step2_token_usage["output_cost"], 6),
                "total_cost": round(step1_token_usage["total_cost"] + step2_token_usage["total_cost"], 6),
                "currency": TOKEN_COST_CURRENCY
            }

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
                    "items_with_image": sum(1 for item in sample_contents if item.get('has_image', False)),
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
                total_duration=total_duration_formatted
            )
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            html_path = output_html_path
            print(f"\n🌐 [HTML Saved]: {output_html_path}")

        # Generate PDF (Using GenerationViewer with Pydantic model directly)
        if output_pdf_path:
            print(f"\n📄 [PDF Generation]: Starting...")
            pdf_html = GenerationViewer.generate_pdf_optimized_html(
                result=final_response,
                project_id=project_id,
                total_items=len(sample_contents),
                executed_at=executed_at,
                total_duration=total_duration_formatted
            )
            if GenerationViewer.generate_pdf_from_html(pdf_html, output_pdf_path):
                pdf_path = output_pdf_path
                print(f"📄 [PDF Saved]: {output_pdf_path}")
            else:
                print(f"❌ [PDF Failed]: Could not generate PDF")

    return step1_response, step2_response, final_response, total_duration, html_path, pdf_path


@pytest.mark.asyncio
async def test_html_generation_from_project_file():
    """
    LLMService 상세 분석 후 HTML 생성 테스트 (유틸리티 사용)
    - 데이터 소스: tests/data/project_365330.json
    - 출력: JSON + HTML (아마존 리뷰 하이라이트 스타일)
    - HTML 출력 경로: tests/data/html/
    """
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
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_dir = os.path.join(current_dir, "..", "data", "html")
    os.makedirs(html_dir, exist_ok=True)

    output_json_path = os.path.join(html_dir, f"project_{project_id}_analysis_{timestamp}.json")
    output_html_path = os.path.join(html_dir, f"project_{project_id}_review_{timestamp}.html")
    # pdf 파일 출력이 필요할 경우 사용
    output_pdf_path = None #os.path.join(html_dir, f"project_{project_id}_report_{timestamp}.pdf")

    # Sample items for testing (랜덤 또는 순차 선택)
    is_all = False
    sample_size = 100

    if not is_all:
        use_random_sampling = True  # True: 랜덤 샘플링, False: 앞에서부터 순차 선택
        if use_random_sampling:
            random.shuffle(content_items)
            print(f"\n📊 Shuffled and sampled {min(sample_size, len(content_items))} items from {len(content_items)} total items")

    test_content_items = content_items if is_all else content_items[:sample_size]

    try:
        step1_res, step2_res, final_res, duration, html_p, pdf_p = \
            await _execute_detailed_analysis_with_html(
                project_id=project_id,
                sample_contents=test_content_items,
                show_content_details=False,
                save_output=True,
                output_json_path=output_json_path,
                output_html_path=output_html_path,
                output_pdf_path=output_pdf_path
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

        print(f"\n✅ Generation Viewer test completed successfully!")
        print(f"   - JSON: {output_json_path}")
        print(f"   - HTML: {output_html_path}")
        if PDF_AVAILABLE and pdf_p:
            print(f"   - PDF:  {pdf_p}")

    except Exception as e:
        pytest.fail(f"Test failed: {e}")
