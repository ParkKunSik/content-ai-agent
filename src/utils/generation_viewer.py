import html
import re
from typing import List, Optional

from src.schemas.models.common.llm_usage_info import LLMUsageInfo
from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult

# PDF 생성을 위한 선택적 임포트
try:
    import weasyprint
    PDF_AVAILABLE = True
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


class GenerationViewer:
    """
    분석 결과를 시각화된 HTML 또는 PDF로 변환하는 유틸리티 클래스.
    """

    @staticmethod
    def _highlight_keyword_in_text(text: str, keyword: str) -> str:
        """
        텍스트에서 키워드를 찾아 <strong> 태그로 감싸기
        """
        if not keyword or keyword not in text:
            return text

        # 대소문자 구분 없이 키워드 찾아서 bold 처리
        pattern = re.escape(keyword)
        return re.sub(f'({pattern})', r'<strong>\1</strong>', text, flags=re.IGNORECASE)

    @staticmethod
    def _get_provider_display_name(provider_name: str = None) -> str:
        """
        Provider 이름을 표시용 이름으로 변환
        """
        from src.core.config.settings import settings

        if provider_name is None:
            provider_name = settings.llm_provider.value

        provider_display_map = {
            "VERTEX_AI": "Vertex AI",
            "OPENAI": "OpenAI",
            "GOOGLE": "Google AI"
        }
        return provider_display_map.get(provider_name.upper(), provider_name)

    @staticmethod
    def generate_pdf_from_html(html_content: str, output_pdf_path: str) -> bool:
        """
        HTML 콘텐츠를 PDF로 변환
        """
        if not PDF_AVAILABLE:
            print("  - PDF generation skipped: No PDF library available (install weasyprint or pdfkit)")
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

    @classmethod
    def generate_pdf_optimized_html(
        cls,
        result: StructuredAnalysisResult,
        project_id: int,
        total_items: int,
        executed_at: str,
        total_duration: str,
        provider_name: str = None
    ) -> str:
        """
        DetailedAnalysisResponse 데이터를 PDF 출력에 최적화된 HTML로 변환
        """
        # Provider 표시명 결정
        provider_display = cls._get_provider_display_name(provider_name)

        summary = result.summary
        categories = result.categories

        html_output = f"""<!DOCTYPE html>
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
            sentiment = category.sentiment_type.value if hasattr(category.sentiment_type, 'value') else str(category.sentiment_type)
            category_name = category.name
            category_summary = category.summary
            pos_count = len(category.positive_contents)
            neg_count = len(category.negative_contents)
            highlights = category.highlights

            # 감정에 따른 텍스트
            sentiment_text = {
                'positive': '긍정적',
                'negative': '부정적', 
                'neutral': '중립적'
            }.get(sentiment, sentiment)

            html_output += f"""
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
                html_output += """
        <div class="highlights-section">
            <div class="highlights-title">주요 하이라이트</div>"""
                
                for highlight in highlights:
                    keyword = highlight.keyword
                    text = highlight.highlight
                    
                    # 키워드를 볼드 처리
                    text_with_bold = cls._highlight_keyword_in_text(text, keyword)
                    
                    html_output += f"""
            <div class="highlight-item">
                <div class="highlight-keyword">"{keyword}"</div>
                <div class="highlight-text">{text_with_bold}</div>
            </div>"""
                
                html_output += """
        </div>"""

            html_output += """
    </div>"""

        # Footer 추가
        html_output += f"""
    <div class="footer">
        Generated by Content AI Agent | Wadiz {provider_display}<br>
        분석 완료: {executed_at}
    </div>
</body>
</html>"""

        return html_output

    @classmethod
    def generate_amazon_style_html(
        cls,
        result: StructuredAnalysisResult,
        project_id: int,
        total_items: int,
        executed_at: str,
        total_duration: str,
        content_type_description: str = "고객 의견",
        provider_name: str = None
    ) -> str:
        """
        DetailedAnalysisResponse 데이터를 아마존 스타일 HTML로 변환
        """
        # Provider 표시명 결정
        provider_display = cls._get_provider_display_name(provider_name)

        summary = result.summary
        categories = result.categories

        html_content = f"""<!DOCTYPE html>
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

        /* 모달 스타일 */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}

        .modal-overlay.active {{
            display: flex;
        }}

        .modal-content {{
            background-color: #fff;
            border-radius: 8px;
            max-width: 600px;
            width: 90%;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        }}

        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid #D5D9D9;
            background-color: #F7FAFA;
            flex-shrink: 0;
        }}

        .modal-title {{
            font-size: 16px;
            font-weight: 700;
            color: #0F1111;
        }}

        .modal-close {{
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

        .modal-close:hover {{
            color: #0F1111;
        }}

        .modal-body {{
            padding: 20px;
            overflow-y: auto;
            line-height: 1.6;
            color: #0F1111;
            font-size: 14px;
            white-space: pre-wrap;
            word-break: break-word;
            flex-grow: 1;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="meta-info">
            프로젝트 ID: {project_id} | 분석 콘텐츠 수: {total_items}개 | 생성일시: {executed_at} | 처리시간: {total_duration}
        </div>
    </div>

    <h1>{content_type_description}</h1>

    <div class="summary-section">
        {summary}
        <span class="ai-badge">ai</span> AI 기반 고객 리뷰 텍스트에서 생성됨
    </div>

    <div class="learn-more">자세히 알아보려면 선택하세요</div>

    <div class="category-grid">
"""

        # 카테고리 버튼들 생성
        for idx, category in enumerate(categories):
            sentiment = category.sentiment_type.value if hasattr(category.sentiment_type, 'value') else str(category.sentiment_type)
            category_display = category.display_highlight
            pos_count = len(category.positive_contents)
            neg_count = len(category.negative_contents)

            # 아이콘 선택
            if sentiment == 'positive':
                icon = '✓'
            elif sentiment == 'negative':
                icon = '✗'
            else:
                icon = '●'

            html_content += f"""        <div class="category-item {sentiment}" onclick="toggleCategory({idx})">
            <span class="category-icon">{icon}</span>
            <span class="category-name">{category_display}</span>
            <span class="category-count">({pos_count + neg_count})</span>
        </div>
"""

        html_content += """    </div>

"""

        # 카테고리 상세 정보 생성
        for idx, category in enumerate(categories):
            category_name = category.name
            category_display = category.display_highlight
            category_summary = category.summary
            pos_count = len(category.positive_contents)
            neg_count = len(category.negative_contents)
            highlights = category.highlights

            html_content += f"""    <div id="category-{idx}" class="category-detail">
        <div class="detail-header">
            <div class="detail-title">{category_display}</div>
            <button class="close-btn" onclick="toggleCategory({idx})">×</button>
        </div>
        <div class="sentiment-counts">
            {pos_count + neg_count}명의 고객이 "<strong>{category_name}</strong>"을(를) 언급
            <span class="positive-text">{pos_count}개 긍정</span>
            <span class="negative-text">{neg_count}개 부정</span>
        </div>
        <div class="category-summary">
            {category_summary}
        </div>
"""

            if highlights:
                html_content += """        <div class="highlights-section">
"""
                for h_idx, highlight in enumerate(highlights[:4]):  # 최대 4개까지만 표시
                    keyword = highlight.keyword
                    text = highlight.highlight
                    content = highlight.content if hasattr(highlight, 'content') and highlight.content else text
                    highlight_id = f"highlight-{idx}-{h_idx}"

                    # 텍스트 길이 제한
                    display_text = text
                    if len(display_text) > 150:
                        display_text = display_text[:150] + '...'

                    # 키워드를 볼드 처리
                    text_with_bold = cls._highlight_keyword_in_text(display_text, keyword)

                    # content/keyword에서 HTML 속성용 이스케이프
                    escaped_content = html.escape(content, quote=True)
                    escaped_keyword = html.escape(keyword, quote=True)

                    html_content += f"""            <div class="highlight-item" id="{highlight_id}" data-keyword="{escaped_keyword}" data-content="{escaped_content}">
                <div class="highlight-keyword">"{keyword}"</div>
                <div class="highlight-text">{text_with_bold} <a href="#" class="read-more" onclick="openModalFromElement('{highlight_id}'); return false;">자세히 보기 ›</a></div>
            </div>
"""
                html_content += """        </div>
"""

            html_content += """    </div>

"""

        # 모달 HTML 추가
        html_content += """
    <!-- 원본 콘텐츠 모달 -->
    <div id="content-modal" class="modal-overlay" onclick="closeModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div class="modal-title" id="modal-title">원본 콘텐츠</div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modal-body"></div>
        </div>
    </div>
"""

        # Footer 추가
        html_content += f"""    <div class="footer">
        Generated by Content AI Agent | Wadiz {provider_display}
    </div>
"""

        # JavaScript 추가
        html_content += """    <script>
        function toggleCategory(index) {
            const detail = document.getElementById(`category-${index}`);
            const isActive = detail.classList.contains('active');

            // 모든 카테고리 상세 정보 닫기
            document.querySelectorAll('.category-detail').forEach(el => {
                el.classList.remove('active');
            });

            // 클릭한 카테고리만 열기 (이미 열려있지 않은 경우)
            if (!isActive) {
                detail.classList.add('active');
                detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }

        function openModalFromElement(elementId) {
            const element = document.getElementById(elementId);
            const keyword = element.dataset.keyword;
            const content = element.dataset.content;
            document.getElementById('modal-title').innerText = '"' + keyword + '" 원본 콘텐츠';
            document.getElementById('modal-body').textContent = content;
            document.getElementById('content-modal').classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function closeModal(event) {
            if (event && event.target !== event.currentTarget) return;
            document.getElementById('content-modal').classList.remove('active');
            document.body.style.overflow = '';
        }

        // ESC 키로 모달 닫기
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeModal();
            }
        });
    </script>
</body>
</html>"""

        return html_content

    @classmethod
    def _highlight_keywords_in_summary(cls, text: str, keywords: List[str]) -> str:
        """
        요약 텍스트에서 키워드들을 볼드 처리
        """
        if not keywords:
            return text

        result = text
        for keyword in keywords:
            if keyword and keyword in result:
                # 첫 번째 매칭만 볼드 처리 (중복 방지)
                result = result.replace(keyword, f'<strong>{keyword}</strong>', 1)
        return result

    @classmethod
    def generate_detail_html(
        cls,
        result: StructuredAnalysisResult,
        project_id: int,
        total_items: int,
        executed_at: str,
        total_duration: str,
        content_type_description: str = "고객 의견",
        provider_name: str = None,
        llm_usages: Optional[List[LLMUsageInfo]] = None
    ) -> str:
        """
        분석 결과를 상세 뷰어 스타일 HTML로 변환
        (viewer_compare.html UI 차용 - LLM 사용량, keywords 볼드, 좋은점/참고사항 포함)

        Args:
            result: 분석 결과 (StructuredAnalysisResult)
            project_id: 프로젝트 ID
            total_items: 분석 대상 콘텐츠 수
            executed_at: 실행 시간
            total_duration: 총 소요 시간
            content_type_description: 콘텐츠 타입 설명
            provider_name: Provider 이름
            llm_usages: LLM 사용량 정보 리스트
        """
        provider_display = cls._get_provider_display_name(provider_name)

        # Keywords를 적용한 요약
        summary_with_keywords = cls._highlight_keywords_in_summary(
            result.summary,
            result.keywords if hasattr(result, 'keywords') and result.keywords else []
        )

        # LLM 사용량 통계 계산
        total_input_tokens = 0
        total_output_tokens = 0
        total_thinking_tokens = 0
        total_cost = 0.0
        total_duration_ms = 0

        if llm_usages:
            for usage in llm_usages:
                total_input_tokens += usage.input_tokens or 0
                total_output_tokens += usage.output_tokens or 0
                total_thinking_tokens += usage.thinking_tokens or 0
                total_cost += usage.total_cost or 0.0
                total_duration_ms += usage.duration_ms or 0

        html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>분석 결과 - 프로젝트 {project_id}</title>
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

        .provider-badge {{
            display: inline-block;
            padding: 4px 10px;
            background-color: #4CAF50;
            color: #fff;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 8px;
        }}

        h1 {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 20px;
        }}

        /* LLM 사용량 섹션 */
        .llm-usage-section {{
            background-color: #F7FAFA;
            border: 1px solid #D5D9D9;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }}

        .llm-usage-title {{
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 12px;
            color: #0F1111;
        }}

        .llm-usage-items {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .llm-usage-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 14px;
            background-color: #fff;
            border-radius: 6px;
            font-size: 13px;
            border: 1px solid #E3E6E6;
        }}

        .usage-step {{
            font-weight: 600;
            color: #0F1111;
        }}

        .usage-model {{
            color: #007185;
            font-family: monospace;
        }}

        .usage-details {{
            display: flex;
            gap: 16px;
            color: #565959;
        }}

        .usage-tokens {{
            color: #0F1111;
        }}

        .usage-thinking {{
            color: #8B5CF6;
            font-weight: 500;
        }}

        .usage-cost {{
            color: #067D62;
            font-weight: 600;
        }}

        .usage-duration {{
            color: #565959;
        }}

        .llm-usage-total {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #D5D9D9;
            font-size: 13px;
        }}

        .usage-total-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 6px;
        }}

        .usage-total-label {{
            font-weight: 600;
        }}

        .usage-total-value {{
            font-family: monospace;
        }}

        /* 인사이트 섹션 */
        .insights-section {{
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
        }}

        @media (max-width: 600px) {{
            .insights-section {{
                flex-direction: column;
            }}
        }}

        .insights-box {{
            flex: 1;
            padding: 14px;
            border-radius: 8px;
        }}

        .insights-box.good-points {{
            background-color: #F0FFF4;
            border: 1px solid #067D62;
        }}

        .insights-box.caution-points {{
            background-color: #FFFAF0;
            border: 1px solid #C7511F;
        }}

        .insights-title {{
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 10px;
        }}

        .insights-title.good {{
            color: #067D62;
        }}

        .insights-title.caution {{
            color: #C7511F;
        }}

        .insights-list {{
            margin: 0;
            padding-left: 18px;
            font-size: 13px;
            line-height: 1.7;
        }}

        .insights-list li {{
            margin-bottom: 6px;
        }}

        /* 요약 섹션 */
        .summary-section {{
            margin-bottom: 24px;
            padding: 16px;
            background-color: #F7FAFA;
            border-radius: 8px;
            line-height: 1.7;
            font-size: 14px;
        }}

        .summary-section strong {{
            font-weight: 700;
            color: #0F1111;
        }}

        .ai-badge {{
            display: inline-block;
            padding: 2px 6px;
            background-color: #E3E6E6;
            border-radius: 4px;
            font-size: 11px;
            margin-left: 8px;
            vertical-align: middle;
        }}

        .learn-more {{
            font-size: 14px;
            font-weight: 700;
            margin: 20px 0 10px 0;
        }}

        /* 카테고리 그리드 */
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

        /* 카테고리 상세 */
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

        .category-summary strong {{
            font-weight: 700;
            color: #0F1111;
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

        /* 모달 스타일 */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}

        .modal-overlay.active {{
            display: flex;
        }}

        .modal-content {{
            background-color: #fff;
            border-radius: 8px;
            max-width: 600px;
            width: 90%;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        }}

        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid #D5D9D9;
            background-color: #F7FAFA;
            flex-shrink: 0;
        }}

        .modal-title {{
            font-size: 16px;
            font-weight: 700;
            color: #0F1111;
        }}

        .modal-close {{
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #565959;
        }}

        .modal-close:hover {{
            color: #0F1111;
        }}

        .modal-body {{
            padding: 20px;
            overflow-y: auto;
            line-height: 1.6;
            color: #0F1111;
            font-size: 14px;
            white-space: pre-wrap;
            word-break: break-word;
            flex-grow: 1;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="meta-info">
            프로젝트 ID: {project_id} | 분석 콘텐츠 수: {total_items}개 | 생성일시: {executed_at} | 처리시간: {total_duration}
            <span class="provider-badge">{provider_display}</span>
        </div>
    </div>

    <h1>{content_type_description}</h1>
"""

        # LLM 사용량 섹션
        if llm_usages:
            html_content += """
    <div class="llm-usage-section">
        <div class="llm-usage-title">📊 LLM 사용량</div>
        <div class="llm-usage-items">
"""
            for usage in llm_usages:
                step_name = f"Step {usage.step}" if usage.step else "Unknown"
                model_name = usage.model or "Unknown"
                tokens = f"{usage.input_tokens:,} / {usage.output_tokens:,}"
                cost = f"${usage.total_cost:.4f}" if usage.total_cost else "-"
                duration = f"{usage.duration_ms:,}ms" if usage.duration_ms else "-"

                # Thinking tokens 표시 (Gemini 2.5 Pro 등)
                thinking_tokens_html = ""
                if usage.thinking_tokens and usage.thinking_tokens > 0:
                    thinking_cost_str = f" (${usage.thinking_cost:.4f})" if usage.thinking_cost else ""
                    thinking_tokens_html = f"""
                    <span class="usage-thinking">🧠 {usage.thinking_tokens:,}{thinking_cost_str}</span>"""

                html_content += f"""            <div class="llm-usage-item">
                <span class="usage-step">{step_name}</span>
                <span class="usage-model">{model_name}</span>
                <div class="usage-details">
                    <span class="usage-tokens">🔢 {tokens}</span>{thinking_tokens_html}
                    <span class="usage-cost">💰 {cost}</span>
                    <span class="usage-duration">⏱️ {duration}</span>
                </div>
            </div>
"""

            # Thinking tokens 총계 표시 (Gemini 2.5 Pro 등)
            thinking_tokens_total_html = ""
            if total_thinking_tokens > 0:
                thinking_tokens_total_html = f" + {total_thinking_tokens:,} (thinking)"

            html_content += f"""        </div>
        <div class="llm-usage-total">
            <div class="usage-total-row">
                <span class="usage-total-label">총 토큰</span>
                <span class="usage-total-value">{total_input_tokens:,} (입력) + {total_output_tokens:,} (출력){thinking_tokens_total_html} = {total_input_tokens + total_output_tokens + total_thinking_tokens:,}</span>
            </div>
            <div class="usage-total-row">
                <span class="usage-total-label">총 비용</span>
                <span class="usage-total-value usage-cost">${total_cost:.4f}</span>
            </div>
            <div class="usage-total-row">
                <span class="usage-total-label">총 소요시간</span>
                <span class="usage-total-value">{total_duration_ms:,}ms ({total_duration_ms / 1000:.1f}초)</span>
            </div>
        </div>
    </div>
"""

        # 요약 섹션 (키워드 볼드 처리)
        html_content += f"""
    <div class="summary-section">
        {summary_with_keywords}
        <span class="ai-badge">AI 분석</span>
    </div>
"""

        # 좋은점 / 참고사항 섹션
        good_points = result.good_points if hasattr(result, 'good_points') and result.good_points else []
        caution_points = result.caution_points if hasattr(result, 'caution_points') and result.caution_points else []

        if good_points or caution_points:
            html_content += """
    <div class="insights-section">
"""
            if good_points:
                html_content += """        <div class="insights-box good-points">
            <div class="insights-title good">👍 좋은 점</div>
            <ul class="insights-list">
"""
                for point in good_points:
                    html_content += f"""                <li>{point}</li>
"""
                html_content += """            </ul>
        </div>
"""

            if caution_points:
                html_content += """        <div class="insights-box caution-points">
            <div class="insights-title caution">⚠️ 참고 사항</div>
            <ul class="insights-list">
"""
                for point in caution_points:
                    html_content += f"""                <li>{point}</li>
"""
                html_content += """            </ul>
        </div>
"""
            html_content += """    </div>
"""

        # 카테고리 그리드
        html_content += """
    <div class="learn-more">카테고리별 상세 분석</div>
    <div class="category-grid">
"""

        categories = result.categories
        for idx, category in enumerate(categories):
            sentiment = category.sentiment_type.value if hasattr(category.sentiment_type, 'value') else str(category.sentiment_type)
            category_display = category.display_highlight
            pos_count = len(category.positive_contents)
            neg_count = len(category.negative_contents)

            if sentiment == 'positive':
                icon = '✓'
            elif sentiment == 'negative':
                icon = '✗'
            else:
                icon = '●'

            html_content += f"""        <div class="category-item {sentiment}" onclick="toggleCategory({idx})">
            <span class="category-icon">{icon}</span>
            <span class="category-name">{category_display}</span>
            <span class="category-count">({pos_count + neg_count})</span>
        </div>
"""

        html_content += """    </div>
"""

        # 카테고리 상세 정보
        for idx, category in enumerate(categories):
            category_name = category.name
            category_display = category.display_highlight
            pos_count = len(category.positive_contents)
            neg_count = len(category.negative_contents)
            highlights = category.highlights

            # 카테고리 요약에 키워드 볼드 처리
            cat_keywords = category.keywords if hasattr(category, 'keywords') and category.keywords else []
            category_summary_with_keywords = cls._highlight_keywords_in_summary(category.summary, cat_keywords)

            html_content += f"""    <div id="category-{idx}" class="category-detail">
        <div class="detail-header">
            <div class="detail-title">{category_display}</div>
            <button class="close-btn" onclick="toggleCategory({idx})">×</button>
        </div>
        <div class="sentiment-counts">
            {pos_count + neg_count}명의 고객이 "<strong>{category_name}</strong>"을(를) 언급
            <span class="positive-text">{pos_count}개 긍정</span>
            <span class="negative-text">{neg_count}개 부정</span>
        </div>
        <div class="category-summary">
            {category_summary_with_keywords}
        </div>
"""

            if highlights:
                html_content += """        <div class="highlights-section">
"""
                for h_idx, highlight in enumerate(highlights[:4]):
                    keyword = highlight.keyword
                    text = highlight.highlight
                    content = highlight.content if hasattr(highlight, 'content') and highlight.content else text
                    highlight_id = f"highlight-{idx}-{h_idx}"

                    display_text = text
                    if len(display_text) > 150:
                        display_text = display_text[:150] + '...'

                    text_with_bold = cls._highlight_keyword_in_text(display_text, keyword)
                    escaped_content = html.escape(content, quote=True)
                    escaped_keyword = html.escape(keyword, quote=True)

                    html_content += f"""            <div class="highlight-item" id="{highlight_id}" data-keyword="{escaped_keyword}" data-content="{escaped_content}">
                <div class="highlight-keyword">"{keyword}"</div>
                <div class="highlight-text">{text_with_bold} <a href="#" class="read-more" onclick="openModalFromElement('{highlight_id}'); return false;">자세히 보기 ›</a></div>
            </div>
"""
                html_content += """        </div>
"""

            html_content += """    </div>
"""

        # 모달
        html_content += """
    <!-- 원본 콘텐츠 모달 -->
    <div id="content-modal" class="modal-overlay" onclick="closeModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div class="modal-title" id="modal-title">원본 콘텐츠</div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modal-body"></div>
        </div>
    </div>
"""

        # Footer
        html_content += f"""
    <div class="footer">
        Generated by Content AI Agent | Wadiz {provider_display}<br>
        분석 완료: {executed_at}
    </div>

    <script>
        function toggleCategory(index) {{
            const detail = document.getElementById(`category-${{index}}`);
            const isActive = detail.classList.contains('active');

            document.querySelectorAll('.category-detail').forEach(el => {{
                el.classList.remove('active');
            }});

            if (!isActive) {{
                detail.classList.add('active');
                detail.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
            }}
        }}

        function openModalFromElement(elementId) {{
            const element = document.getElementById(elementId);
            const keyword = element.dataset.keyword;
            const content = element.dataset.content;
            document.getElementById('modal-title').innerText = '"' + keyword + '" 원본 콘텐츠';
            document.getElementById('modal-body').textContent = content;
            document.getElementById('content-modal').classList.add('active');
            document.body.style.overflow = 'hidden';
        }}

        function closeModal(event) {{
            if (event && event.target !== event.currentTarget) return;
            document.getElementById('content-modal').classList.remove('active');
            document.body.style.overflow = '';
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                closeModal();
            }}
        }});
    </script>
</body>
</html>"""

        return html_content

    @staticmethod
    def generate_usage_statistics_html(
        llm_usages: List[LLMUsageInfo],
        title: str = "LLM 사용량 통계",
        provider_name: str = None,
        executed_at: str = None,
        wall_clock_duration_ms: int = None,
        concurrent_limit: int = None,
        total_projects: int = None,
        total_content_items: int = None,
        per_project_stats: List[dict] = None
    ) -> str:
        """
        LLM 사용량 통계를 보여주는 HTML 생성

        Args:
            llm_usages: LLMUsageInfo 리스트
            title: 페이지 제목
            provider_name: Provider 이름
            executed_at: 실행 시각
            wall_clock_duration_ms: 실제 경과 시간 (밀리초)
            concurrent_limit: 동시 실행 수
            total_projects: 총 프로젝트 수
            total_content_items: 총 콘텐츠 수
            per_project_stats: 프로젝트별 통계 리스트

        Returns:
            HTML 문자열
        """
        # 토큰/비용 합산
        total_input_tokens = sum(u.input_tokens or 0 for u in llm_usages)
        total_output_tokens = sum(u.output_tokens or 0 for u in llm_usages)
        total_thinking_tokens = sum(u.thinking_tokens or 0 for u in llm_usages)
        total_cost = sum(u.total_cost or 0.0 for u in llm_usages)
        llm_total_duration_ms = sum(u.duration_ms or 0 for u in llm_usages)

        # 비용 세부 합산
        total_input_cost = sum(u.input_cost or 0.0 for u in llm_usages)
        total_output_cost = sum(u.output_cost or 0.0 for u in llm_usages)
        total_thinking_cost = sum(u.thinking_cost or 0.0 for u in llm_usages)

        # 시간 포맷팅
        def format_duration(ms: int) -> str:
            if ms is None:
                return "-"
            total_seconds = ms / 1000
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            secs = int(total_seconds % 60)
            millis = int((total_seconds - int(total_seconds)) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

        # 병렬 효율 계산
        parallelism_efficiency = ""
        if wall_clock_duration_ms and wall_clock_duration_ms > 0 and llm_total_duration_ms > 0:
            efficiency = llm_total_duration_ms / wall_clock_duration_ms
            parallelism_efficiency = f"{efficiency:.1f}x"

        # Provider 표시명
        provider_display = GenerationViewer._get_provider_display_name(provider_name)

        html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f5f5f5;
            color: #0F1111;
            line-height: 1.6;
            padding: 24px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            background: linear-gradient(135deg, #232F3E 0%, #37475A 100%);
            color: white;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 24px;
        }}

        .header h1 {{
            font-size: 24px;
            margin-bottom: 12px;
        }}

        .header-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            font-size: 14px;
            opacity: 0.9;
        }}

        .header-meta span {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .provider-badge {{
            background: #FF9900;
            color: #0F1111;
            padding: 4px 12px;
            border-radius: 16px;
            font-weight: 600;
            font-size: 12px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}

        .stat-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }}

        .stat-card h3 {{
            font-size: 14px;
            color: #565959;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .stat-value {{
            font-size: 28px;
            font-weight: 700;
            color: #0F1111;
        }}

        .stat-value.cost {{
            color: #067D62;
        }}

        .stat-value.thinking {{
            color: #8B5CF6;
        }}

        .stat-detail {{
            font-size: 13px;
            color: #565959;
            margin-top: 8px;
        }}

        .usage-table {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            margin-bottom: 24px;
            overflow-x: auto;
        }}

        .usage-table h3 {{
            font-size: 16px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}

        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #E7E7E7;
        }}

        th {{
            background: #F7F7F7;
            font-weight: 600;
            color: #565959;
            font-size: 12px;
            text-transform: uppercase;
        }}

        tr:hover {{
            background: #FAFAFA;
        }}

        .token-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}

        .token-badge.input {{
            background: #E3F2FD;
            color: #1565C0;
        }}

        .token-badge.output {{
            background: #E8F5E9;
            color: #2E7D32;
        }}

        .token-badge.thinking {{
            background: #EDE7F6;
            color: #7C3AED;
        }}

        .cost-cell {{
            color: #067D62;
            font-weight: 600;
        }}

        .project-stats {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }}

        .project-stats h3 {{
            font-size: 16px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .project-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }}

        .project-item {{
            background: #F7F7F7;
            padding: 12px 16px;
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .project-id {{
            font-weight: 600;
            color: #0F1111;
        }}

        .project-count {{
            font-size: 13px;
            color: #565959;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="header-meta">
                <span class="provider-badge">{provider_display}</span>"""

        if executed_at:
            html_content += f"""
                <span>📅 {executed_at}</span>"""

        if total_projects:
            html_content += f"""
                <span>📁 {total_projects}개 프로젝트</span>"""

        if total_content_items:
            html_content += f"""
                <span>📝 {total_content_items:,}건 콘텐츠</span>"""

        if concurrent_limit:
            html_content += f"""
                <span>⚡ 동시 실행 {concurrent_limit}개</span>"""

        html_content += """
            </div>
        </div>

        <div class="stats-grid">"""

        # 토큰 통계 카드
        html_content += f"""
            <div class="stat-card">
                <h3>🔢 총 토큰</h3>
                <div class="stat-value">{total_input_tokens + total_output_tokens + total_thinking_tokens:,}</div>
                <div class="stat-detail">
                    입력: {total_input_tokens:,} | 출력: {total_output_tokens:,}"""

        if total_thinking_tokens > 0:
            html_content += f""" | Thinking: {total_thinking_tokens:,}"""

        html_content += """
                </div>
            </div>"""

        # 비용 통계 카드
        html_content += f"""
            <div class="stat-card">
                <h3>💰 총 비용</h3>
                <div class="stat-value cost">${total_cost:.4f}</div>
                <div class="stat-detail">
                    입력: ${total_input_cost:.4f} | 출력: ${total_output_cost:.4f}"""

        if total_thinking_cost > 0:
            html_content += f""" | Thinking: ${total_thinking_cost:.4f}"""

        html_content += """
                </div>
            </div>"""

        # 시간 통계 카드
        if wall_clock_duration_ms:
            html_content += f"""
            <div class="stat-card">
                <h3>⏱️ 실행 시간</h3>
                <div class="stat-value">{format_duration(wall_clock_duration_ms)}</div>
                <div class="stat-detail">
                    LLM 호출 합계: {format_duration(llm_total_duration_ms)}"""

            if parallelism_efficiency:
                html_content += f""" | 병렬 효율: {parallelism_efficiency}"""

            html_content += """
                </div>
            </div>"""

        # Thinking 토큰 카드 (있는 경우만)
        if total_thinking_tokens > 0:
            thinking_ratio = (total_thinking_tokens / total_output_tokens * 100) if total_output_tokens > 0 else 0
            html_content += f"""
            <div class="stat-card">
                <h3>🧠 Thinking 토큰</h3>
                <div class="stat-value thinking">{total_thinking_tokens:,}</div>
                <div class="stat-detail">
                    출력 대비 {thinking_ratio:.1f}% | 비용: ${total_thinking_cost:.4f}
                </div>
            </div>"""

        html_content += """
        </div>"""

        # LLM 사용량 상세 테이블
        html_content += """
        <div class="usage-table">
            <h3>📊 LLM 호출 상세</h3>
            <table>
                <thead>
                    <tr>
                        <th>Step</th>
                        <th>모델</th>
                        <th>입력 토큰</th>
                        <th>출력 토큰</th>"""

        if total_thinking_tokens > 0:
            html_content += """
                        <th>Thinking 토큰</th>"""

        html_content += """
                        <th>비용</th>
                        <th>소요 시간</th>
                    </tr>
                </thead>
                <tbody>"""

        for usage in llm_usages:
            step_name = f"Step {usage.step}" if usage.step else "-"
            model_name = usage.model or "-"
            cost = f"${usage.total_cost:.4f}" if usage.total_cost else "-"
            duration = f"{usage.duration_ms:,}ms" if usage.duration_ms else "-"

            html_content += f"""
                    <tr>
                        <td>{step_name}</td>
                        <td>{model_name}</td>
                        <td><span class="token-badge input">{usage.input_tokens:,}</span></td>
                        <td><span class="token-badge output">{usage.output_tokens:,}</span></td>"""

            if total_thinking_tokens > 0:
                thinking_display = f'<span class="token-badge thinking">{usage.thinking_tokens:,}</span>' if usage.thinking_tokens else "-"
                html_content += f"""
                        <td>{thinking_display}</td>"""

            html_content += f"""
                        <td class="cost-cell">{cost}</td>
                        <td>{duration}</td>
                    </tr>"""

        html_content += """
                </tbody>
            </table>
        </div>"""

        # 프로젝트별 통계 (있는 경우)
        if per_project_stats:
            html_content += """
        <div class="project-stats">
            <h3>📁 프로젝트별 통계</h3>
            <div class="project-grid">"""

            for stat in per_project_stats:
                project_id = stat.get("project_id", "-")
                content_count = stat.get("content_count", 0)
                categories_count = stat.get("categories_count", 0)

                html_content += f"""
                <div class="project-item">
                    <span class="project-id">{project_id}</span>
                    <span class="project-count">{content_count}건 / {categories_count}카테고리</span>
                </div>"""

            html_content += """
            </div>
        </div>"""

        html_content += """
    </div>
</body>
</html>"""

        return html_content
