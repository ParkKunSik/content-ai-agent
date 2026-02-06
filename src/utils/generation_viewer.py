import re
import html

from src.schemas.models.prompt.structured_analysis_response import StructuredAnalysisResponse

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
        result: StructuredAnalysisResponse,
        project_id: int,
        total_items: int,
        executed_at: str,
        total_duration: str
    ) -> str:
        """
        DetailedAnalysisResponse 데이터를 PDF 출력에 최적화된 HTML로 변환
        """
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
            category_name = category.category
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
        Generated by Content AI Agent | Wadiz Vertex AI<br>
        분석 완료: {executed_at}
    </div>
</body>
</html>"""

        return html_output

    @classmethod
    def generate_amazon_style_html(
        cls,
        result: StructuredAnalysisResponse,
        project_id: int,
        total_items: int,
        executed_at: str,
        total_duration: str,
        content_type_description: str = "고객 의견"
    ) -> str:
        """
        DetailedAnalysisResponse 데이터를 아마존 스타일 HTML로 변환
        """
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
            category_name = category.category
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

        # JavaScript 및 Footer 추가
        html_content += """    <div class="footer">
        Generated by Content AI Agent | Wadiz Vertex AI
    </div>

    <script>
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
        