import json
import os
import random
import time
from datetime import datetime, timedelta

import pytest

from src.core.config import settings
from src.core.model_factory import ModelFactory
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.services.llm_service import LLMService
from src.utils.prompt_manager import PromptManager

# PDF 생성을 위한 선택적 임포트
try:
    import weasyprint
    PDF_AVAILABLE = False
    PDF_LIB = "weasyprint"
except ImportError:
    weasyprint = None
    try:
        import pdfkit
        PDF_AVAILABLE = True
        PDF_LIB = "pdfkit"
    except ImportError:
        pdfkit = None
        PDF_AVAILABLE = False
        PDF_LIB = None

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


def _generate_pdf_from_html(html_content: str, output_pdf_path: str) -> bool:
    """
    HTML 콘텐츠를 PDF로 변환
    
    Args:
        html_content: HTML 문자열
        output_pdf_path: PDF 출력 경로
        
    Returns:
        bool: 성공 여부
    """
    if not PDF_AVAILABLE:
        print(f"  - PDF generation skipped: No PDF library available (install weasyprint or pdfkit)")
        return False
    
    try:
        if PDF_LIB == "weasyprint":
            # WeasyPrint를 사용한 PDF 생성
            html_doc = weasyprint.HTML(string=html_content)
            html_doc.write_pdf(output_pdf_path)
            
        elif PDF_LIB == "pdfkit":
            # pdfkit을 사용한 PDF 생성
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None
            }
            pdfkit.from_string(html_content, output_pdf_path, options=options)
        
        return True
        
    except Exception as e:
        print(f"  - PDF generation failed: {e}")
        return False


def _highlight_keyword_in_text(text: str, keyword: str) -> str:
    """
    텍스트에서 키워드를 찾아 <strong> 태그로 감싸기

    Args:
        text: 원본 텍스트
        keyword: 강조할 키워드

    Returns:
        키워드가 bold 처리된 HTML 텍스트
    """
    if not keyword or keyword not in text:
        return text

    # 대소문자 구분 없이 키워드 찾아서 bold 처리
    import re
    pattern = re.escape(keyword)
    return re.sub(f'({pattern})', r'<strong>\1</strong>', text, flags=re.IGNORECASE)


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


def _generate_pdf_optimized_html(data: dict) -> str:
    """JSON 데이터를 PDF 출력에 최적화된 HTML로 변환"""
    
    final_result = data.get('final_result', {})
    summary = final_result.get('summary', '')
    categories = final_result.get('categories', [])

    # execution_time 정보 추가
    exec_time = data.get('execution_time', {})
    executed_at = exec_time.get('executed_at', '')
    total_duration = exec_time.get('total_duration_formatted', '')

    # input_summary 정보 추가
    input_summary = data.get('input_summary', {})
    total_items = input_summary.get('total_items', 0)
    project_id = input_summary.get('project_id', 0)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>고객 리뷰 요약 - 프로젝트 {project_id}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm 1.5cm;
        }}
        
        body {{
            font-family: "Malgun Gothic", "맑은 고딕", Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.4;
            color: #333;
            margin: 0;
            padding: 0;
        }}

        .header {{
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }}

        .meta-info {{
            font-size: 9pt;
            color: #666;
            margin-bottom: 8px;
        }}

        h1 {{
            font-size: 18pt;
            font-weight: bold;
            margin: 0 0 15px 0;
            color: #2c3e50;
        }}

        .summary-section {{
            margin-bottom: 25px;
            padding: 12px;
            background-color: #f8f9fa;
            border-left: 4px solid #007185;
            line-height: 1.6;
        }}

        .ai-badge {{
            display: inline-block;
            padding: 2px 6px;
            background-color: #e9ecef;
            border-radius: 3px;
            font-size: 8pt;
            margin-left: 8px;
        }}

        .category-section {{
            margin-bottom: 20px;
            page-break-inside: avoid;
        }}

        .category-header {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            padding: 8px 12px;
            background-color: #f1f3f4;
            border-radius: 4px;
        }}

        .category-title {{
            font-size: 12pt;
            font-weight: bold;
            color: #2c3e50;
            margin-right: 10px;
        }}

        .sentiment-badge {{
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 9pt;
            font-weight: bold;
            text-transform: uppercase;
        }}

        .sentiment-positive {{
            background: #d4edda;
            color: #155724;
        }}

        .sentiment-negative {{
            background: #f8d7da;
            color: #721c24;
        }}

        .sentiment-neutral {{
            background: #e2e3e5;
            color: #383d41;
        }}

        .sentiment-counts {{
            font-size: 9pt;
            color: #666;
            margin-bottom: 8px;
        }}

        .category-summary {{
            margin-bottom: 12px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
            line-height: 1.5;
        }}

        .highlights-section {{
            margin-top: 10px;
        }}

        .highlights-title {{
            font-size: 10pt;
            font-weight: bold;
            margin-bottom: 8px;
            color: #495057;
        }}

        .highlight-item {{
            margin-bottom: 8px;
            padding: 8px;
            background-color: #fff;
            border-left: 3px solid #007185;
            font-size: 10pt;
        }}

        .highlight-keyword {{
            font-weight: bold;
            color: #007185;
            margin-bottom: 4px;
        }}

        .highlight-text {{
            color: #555;
            line-height: 1.4;
        }}

        .highlight-text strong {{
            font-weight: bold;
            color: #2c3e50;
        }}

        .footer {{
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #dee2e6;
            font-size: 9pt;
            color: #6c757d;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="meta-info">
            프로젝트 ID: {project_id} | 분석 콘텐츠 수: {total_items}개 | 생성일시: {executed_at} | 처리시간: {total_duration}
        </div>
        <h1>고객 의견 분석 보고서</h1>
    </div>

    <div class="summary-section">
        {summary}
        <span class="ai-badge">AI 분석</span>
    </div>

    <h2 style="font-size: 14pt; margin-bottom: 15px; color: #2c3e50;">카테고리별 상세 분석</h2>
"""

    # 카테고리별 상세 정보 생성
    for category in categories:
        sentiment = category.get('sentiment_type', 'neutral')
        category_name = category.get('category', '')
        category_summary = category.get('summary', '')
        pos_count = len(category.get('positive_contents', []))
        neg_count = len(category.get('negative_contents', []))
        highlights = category.get('highlights', [])

        # 감정에 따른 텍스트
        sentiment_text = {
            'positive': '긍정적',
            'negative': '부정적', 
            'neutral': '중립적'
        }.get(sentiment, sentiment)

        html += f"""
    <div class="category-section">
        <div class="category-header">
            <div class="category-title">{category_name}</div>
            <div class="sentiment-badge sentiment-{sentiment}">{sentiment_text}</div>
        </div>
        <div class="sentiment-counts">
            총 {pos_count + neg_count}개 의견 (긍정 {pos_count}개, 부정 {neg_count}개)
        </div>
        <div class="category-summary">
            {category_summary}
        </div>"""

        if highlights:
            html += """
        <div class="highlights-section">
            <div class="highlights-title">주요 하이라이트</div>"""
            
            for highlight in highlights:
                keyword = highlight.get('keyword', '')
                text = highlight.get('highlight', '')
                
                # 키워드를 볼드 처리
                text_with_bold = _highlight_keyword_in_text(text, keyword)
                
                html += f"""
            <div class="highlight-item">
                <div class="highlight-keyword">"{keyword}"</div>
                <div class="highlight-text">{text_with_bold}</div>
            </div>"""
            
            html += """
        </div>"""

        html += """
    </div>"""

    # Footer 추가
    html += f"""
    <div class="footer">
        Generated by Content AI Agent | Wadiz Vertex AI<br>
        분석 완료: {executed_at}
    </div>
</body>
</html>"""

    return html


def _generate_amazon_style_html(data: dict) -> str:
    """JSON 데이터를 아마존 스타일 HTML로 변환"""

    final_result = data.get('final_result', {})
    summary = final_result.get('summary', '')
    categories = final_result.get('categories', [])

    # execution_time 정보 추가
    exec_time = data.get('execution_time', {})
    executed_at = exec_time.get('executed_at', '')
    total_duration = exec_time.get('total_duration_formatted', '')

    # input_summary 정보 추가
    input_summary = data.get('input_summary', {})
    total_items = input_summary.get('total_items', 0)
    project_id = input_summary.get('project_id', 0)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>고객 리뷰 요약 - 프로젝트 {project_id}</title>
    <style>
        body {{
            font-family: "Amazon Ember", Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fff;
            color: #0F1111;
        }}

        .header {{
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #D5D9D9;
        }}

        .meta-info {{
            font-size: 12px;
            color: #565959;
            margin-bottom: 10px;
        }}

        h1 {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 20px;
        }}

        .summary-section {{
            margin-bottom: 30px;
            line-height: 1.6;
        }}

        .ai-badge {{
            display: inline-block;
            padding: 2px 6px;
            background-color: #f0f0f0;
            border-radius: 4px;
            font-size: 12px;
            margin-left: 8px;
            vertical-align: middle;
        }}

        .learn-more {{
            font-size: 14px;
            font-weight: 700;
            margin: 20px 0 10px 0;
        }}

        .category-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 30px;
        }}

        .category-item {{
            display: flex;
            align-items: center;
            padding: 8px 12px;
            background-color: #fff;
            border: 1px solid #D5D9D9;
            border-radius: 8px;
            cursor: pointer;
            transition: background-color 0.2s;
        }}

        .category-item:hover {{
            background-color: #F7FAFA;
            border-color: #008296;
        }}

        .category-item.positive {{
            border-color: #067D62;
        }}

        .category-item.negative {{
            border-color: #CC0C39;
        }}

        .category-icon {{
            margin-right: 8px;
            font-size: 16px;
        }}

        .positive .category-icon {{
            color: #067D62;
        }}

        .negative .category-icon {{
            color: #CC0C39;
        }}

        .neutral .category-icon {{
            color: #565959;
        }}

        .category-name {{
            color: #007185;
            font-size: 14px;
            margin-right: 4px;
        }}

        .category-count {{
            color: #565959;
            font-size: 14px;
        }}

        .category-detail {{
            display: none;
            margin-top: 20px;
            padding: 20px;
            background-color: #F7FAFA;
            border-radius: 8px;
            border: 1px solid #D5D9D9;
        }}

        .category-detail.active {{
            display: block;
        }}

        .detail-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid #D5D9D9;
        }}

        .detail-title {{
            font-size: 18px;
            font-weight: 700;
        }}

        .close-btn {{
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #565959;
            padding: 0;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .close-btn:hover {{
            color: #0F1111;
        }}

        .sentiment-counts {{
            font-size: 14px;
            color: #565959;
            margin-bottom: 12px;
        }}

        .sentiment-counts .positive-text {{
            color: #067D62;
        }}

        .sentiment-counts .negative-text {{
            color: #CC0C39;
        }}

        .category-summary {{
            margin-bottom: 16px;
            line-height: 1.6;
        }}

        .highlights-section {{
            margin-top: 16px;
        }}

        .highlight-item {{
            margin-bottom: 12px;
            padding: 12px;
            background-color: #fff;
            border-radius: 4px;
            border-left: 3px solid #067D62;
        }}

        .highlight-keyword {{
            font-weight: 700;
            margin-bottom: 4px;
        }}

        .highlight-text {{
            color: #565959;
            font-size: 13px;
            line-height: 1.5;
        }}

        .highlight-text strong {{
            font-weight: 900;
            color: #0F1111;
        }}

        .read-more {{
            color: #007185;
            text-decoration: none;
            font-size: 13px;
            margin-left: 4px;
        }}

        .read-more:hover {{
            color: #C7511F;
            text-decoration: underline;
        }}

        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #D5D9D9;
            font-size: 12px;
            color: #565959;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="meta-info">
            프로젝트 ID: {project_id} | 분석 콘텐츠 수: {total_items}개 | 생성일시: {executed_at} | 처리시간: {total_duration}
        </div>
    </div>

    <h1>고객 의견</h1>

    <div class="summary-section">
        {summary}
        <span class="ai-badge">ai</span> AI 기반 고객 리뷰 텍스트에서 생성됨
    </div>

    <div class="learn-more">자세히 알아보려면 선택하세요</div>

    <div class="category-grid">
"""

    # 카테고리 버튼들 생성
    for idx, category in enumerate(categories):
        sentiment = category.get('sentiment_type', 'neutral')
        category_name = category.get('category', '')
        pos_count = len(category.get('positive_contents', []))
        neg_count = len(category.get('negative_contents', []))

        # 아이콘 선택
        if sentiment == 'positive':
            icon = '✓'
        elif sentiment == 'negative':
            icon = '○'
        else:
            icon = '—'

        html += f"""        <div class="category-item {sentiment}" onclick="toggleCategory({idx})">
            <span class="category-icon">{icon}</span>
            <span class="category-name">{category_name}</span>
            <span class="category-count">({pos_count + neg_count})</span>
        </div>
"""

    html += """    </div>

"""

    # 카테고리 상세 정보 생성
    for idx, category in enumerate(categories):
        category_name = category.get('category', '')
        category_summary = category.get('summary', '')
        pos_count = len(category.get('positive_contents', []))
        neg_count = len(category.get('negative_contents', []))
        highlights = category.get('highlights', [])

        html += f"""    <div id="category-{idx}" class="category-detail">
        <div class="detail-header">
            <div class="detail-title">{category_name}</div>
            <button class="close-btn" onclick="toggleCategory({idx})">×</button>
        </div>
        <div class="sentiment-counts">
            {pos_count + neg_count}명의 고객이 "{category_name}"을(를) 언급
            <span class="positive-text">{pos_count}개 긍정</span>
            <span class="negative-text">{neg_count}개 부정</span>
        </div>
        <div class="category-summary">
            {category_summary}
        </div>
"""

        if highlights:
            html += """        <div class="highlights-section">
"""
            for highlight in highlights[:4]:  # 최대 4개까지만 표시
                keyword = highlight.get('keyword', '')
                text = highlight.get('highlight', '')

                # 텍스트 길이 제한
                if len(text) > 150:
                    text = text[:150] + '...'

                # 키워드를 볼드 처리
                text_with_bold = _highlight_keyword_in_text(text, keyword)

                html += f"""            <div class="highlight-item">
                <div class="highlight-keyword">"{keyword}"</div>
                <div class="highlight-text">{text_with_bold} <a href="#" class="read-more">자세히 보기 ›</a></div>
            </div>
"""
            html += """        </div>
"""

        html += """    </div>

"""

    # JavaScript 및 Footer 추가
    html += f"""    <div class="footer">
        Generated by Content AI Agent | Wadiz Vertex AI
    </div>

    <script>
        function toggleCategory(index) {{
            const detail = document.getElementById(`category-${{index}}`);
            const isActive = detail.classList.contains('active');

            // 모든 카테고리 상세 정보 닫기
            document.querySelectorAll('.category-detail').forEach(el => {{
                el.classList.remove('active');
            }});

            // 클릭한 카테고리만 열기 (이미 열려있지 않은 경우)
            if (!isActive) {{
                detail.classList.add('active');
                detail.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
            }}
        }}
    </script>
</body>
</html>"""

    return html


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
    상세 분석 플로우 실행 후 HTML/PDF 생성

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
    ModelFactory.initialize()
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

    print(f"\n✅ [Final Merged Result] (Duration: {total_duration:.2f}s)")
    print(f"\n🕒 [Total Execution Time]: {total_duration:.2f}s")

    # 6. Save JSON, HTML and PDF if requested
    html_path = None
    pdf_path = None
    if save_output:
        # Prepare output data
        step1_result = step1_response.model_dump()
        step1_result["execution_time_seconds"] = round(step1_duration, 2)
        step1_result["execution_time_formatted"] = _format_duration(step1_duration)

        step2_result = step2_response.model_dump()
        step2_result["execution_time_seconds"] = round(step2_duration, 2)
        step2_result["execution_time_formatted"] = _format_duration(step2_duration)

        final_result = final_response.model_dump()
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
                "total_duration_formatted": _format_duration(total_duration),
                "executed_at": datetime.now().isoformat()
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

        # Save JSON
        if output_json_path:
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 [JSON Saved]: {output_json_path}")

        # Generate and save HTML
        if output_html_path:
            html_data = dict(output_data)
            html_data.pop("token_usage", None)
            html_content = _generate_amazon_style_html(html_data)
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            html_path = output_html_path
            print(f"\n🌐 [HTML Saved]: {output_html_path}")

        # Generate and save PDF
        if output_pdf_path:
            print(f"\n📄 [PDF Generation]: Starting...")
            html_data = dict(output_data)
            html_data.pop("token_usage", None)
            
            # PDF용으로 최적화된 HTML 생성
            pdf_html_content = _generate_pdf_optimized_html(html_data)
            
            # PDF 생성
            pdf_success = _generate_pdf_from_html(pdf_html_content, output_pdf_path)
            if pdf_success:
                pdf_path = output_pdf_path
                print(f"📄 [PDF Saved]: {output_pdf_path}")
            else:
                print(f"❌ [PDF Failed]: Could not generate PDF")

    return step1_response, step2_response, final_response, total_duration, html_path, pdf_path


@pytest.mark.asyncio
async def test_html_generation_from_project_file():
    """
    LLMService 상세 분석 후 HTML 생성 테스트
    - 데이터 소스: tests/data/project_365330.json
    - 출력: JSON + HTML (아마존 리뷰 하이라이트 스타일)
    - HTML 출력 경로: tests/data/html/
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

    # Prepare output paths
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_dir = os.path.join(current_dir, "..", "data", "html")

    # Ensure html directory exists
    os.makedirs(html_dir, exist_ok=True)

    output_json_path = os.path.join(
        html_dir,
        f"project_{project_id}_analysis_{timestamp}.json"
    )

    output_html_path = os.path.join(
        html_dir,
        f"project_{project_id}_review_{timestamp}.html"
    )

    output_pdf_path = os.path.join(
        html_dir,
        f"project_{project_id}_report_{timestamp}.pdf"
    )

    is_all = False
    # Sample items for testing (랜덤 또는 순차 선택)
    sample_size = 500

    if is_all:
        use_random_sampling = True  # True: 랜덤 샘플링, False: 앞에서부터 순차 선택
        if use_random_sampling:
            random.shuffle(content_items)
            print(f"\n📊 Shuffled and sampled {min(sample_size, len(content_items))} items from {len(content_items)} total items")

    test_content_items = content_items if is_all else content_items[:sample_size]

    try:
        step1_response, step2_response, final_response, total_duration, html_path, pdf_path = \
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
        assert step1_response is not None
        assert len(step1_response.categories) > 0
        assert step2_response is not None
        assert len(step2_response.summary) > 0
        assert os.path.exists(output_json_path), "JSON output file should be created"
        assert os.path.exists(output_html_path), "HTML output file should be created"
        assert html_path == output_html_path

        # PDF 검증 (PDF 라이브러리가 있는 경우에만)
        if PDF_AVAILABLE and pdf_path:
            assert os.path.exists(output_pdf_path), "PDF output file should be created"
            assert pdf_path == output_pdf_path

        print(f"\n✅ Test completed successfully!")
        print(f"   - JSON: {output_json_path}")
        print(f"   - HTML: {output_html_path}")
        if PDF_AVAILABLE and pdf_path:
            print(f"   - PDF:  {output_pdf_path}")
        elif not PDF_AVAILABLE:
            print(f"   - PDF:  Skipped (install weasyprint or pdfkit)")

    except Exception as e:
        pytest.fail(f"HTML generation test failed: {e}")
