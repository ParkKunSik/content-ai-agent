"""
StructuredAnalysisRefineResult 기반 HTML 생성기

원본: src/viewer/refine_result_renderer.py
"""
import html
import re
from typing import List, Optional

from viewer.schemas.models import AnalysisResult


class RefineResultRenderer:
    """AnalysisResult 기반 HTML 생성기"""

    @staticmethod
    def _highlight_keyword_in_text(text: str, keyword: str) -> str:
        """
        텍스트에서 키워드를 찾아 <strong> 태그로 감싸기
        """
        if not keyword or keyword not in text:
            return text

        pattern = re.escape(keyword)
        return re.sub(f"({pattern})", r"<strong>\1</strong>", text, flags=re.IGNORECASE)

    @staticmethod
    def _highlight_keywords_in_summary(summary: str, keywords: List[str]) -> str:
        """
        summary에서 keywords에 해당하는 부분을 <strong> 태그로 감싸기
        """
        if not keywords:
            return summary

        result = summary
        for keyword in keywords:
            if keyword in result:
                # 대소문자 구분하여 원본 유지
                pattern = re.escape(keyword)
                result = re.sub(
                    f"({pattern})",
                    r"<strong>\1</strong>",
                    result,
                    count=1  # 첫 번째 매칭만 처리 (중복 방지)
                )
        return result

    @staticmethod
    def _render_insights_section(
        good_points: List[str],
        caution_points: List[str]
    ) -> str:
        """
        Good Points와 Caution Points를 HTML로 렌더링
        """
        if not good_points and not caution_points:
            return ""

        html_parts = ['<div class="insights-section">']

        if good_points:
            html_parts.append('<div class="good-points">')
            html_parts.append('<h4 class="insights-title good">좋은 점</h4>')
            html_parts.append('<ul>')
            for point in good_points:
                html_parts.append(f'<li>{point}</li>')
            html_parts.append('</ul>')
            html_parts.append('</div>')

        if caution_points:
            html_parts.append('<div class="caution-points">')
            html_parts.append('<h4 class="insights-title caution">참고 사항</h4>')
            html_parts.append('<ul>')
            for point in caution_points:
                html_parts.append(f'<li>{point}</li>')
            html_parts.append('</ul>')
            html_parts.append('</div>')

        html_parts.append('</div>')
        return '\n'.join(html_parts)

    @classmethod
    def generate_amazon_style_html(
        cls,
        result: AnalysisResult,
        project_id: int,
        content_type: str,
        executed_at: str,
        content_type_description: str = "고객 의견",
        project_title: Optional[str] = None,
        project_thumbnail_url: Optional[str] = None,
        project_link: Optional[str] = None,
    ) -> str:
        """
        AnalysisResult 데이터를 Amazon 스타일 HTML로 변환

        Args:
            result: 정제된 분석 결과
            project_id: 프로젝트 ID
            content_type: 콘텐츠 타입 (REVIEW, QNA 등)
            executed_at: 실행 시간
            content_type_description: 콘텐츠 타입 설명 (헤더용)
            project_title: 프로젝트 제목 (Wadiz API)
            project_thumbnail_url: 프로젝트 썸네일 이미지 URL (Wadiz API)
            project_link: 프로젝트 상세 링크

        Returns:
            HTML 문자열
        """
        summary = result.summary
        categories = result.categories

        # 전체 항목 수 계산
        total_items = sum(cat.positive_count + cat.negative_count for cat in categories)

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

        .project-info-section {{
            display: flex;
            align-items: center;
            margin-bottom: 24px;
            padding: 16px;
            background-color: #F7FAFA;
            border-radius: 8px;
            border: 1px solid #D5D9D9;
        }}

        .project-info-content {{
            flex: 1;
        }}

        .project-title {{
            font-size: 18px;
            font-weight: 700;
            color: #0F1111;
        }}

        .project-title-link {{
            color: #007185;
            text-decoration: none;
        }}

        .project-title-link:hover {{
            color: #C7511F;
            text-decoration: underline;
        }}

        .project-thumbnail {{
            width: 120px;
            height: 120px;
            object-fit: cover;
            border-radius: 8px;
            margin-right: 16px;
            flex-shrink: 0;
        }}

        .summary-section {{
            margin-bottom: 30px;
            line-height: 1.6;
        }}

        .summary-section strong {{
            font-weight: 700;
            color: #0F1111;
        }}

        .insights-section {{
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
        }}

        .good-points, .caution-points {{
            flex: 1;
            padding: 16px;
            border-radius: 8px;
        }}

        .good-points {{
            background-color: #F0FFF4;
            border: 1px solid #067D62;
        }}

        .caution-points {{
            background-color: #FFFAF0;
            border: 1px solid #C7511F;
        }}

        .insights-title {{
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 12px;
        }}

        .insights-title.good {{
            color: #067D62;
        }}

        .insights-title.caution {{
            color: #C7511F;
        }}

        .insights-section ul {{
            margin: 0;
            padding-left: 20px;
        }}

        .insights-section li {{
            margin-bottom: 8px;
            line-height: 1.5;
            font-size: 14px;
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
            프로젝트 ID: {project_id} | 콘텐츠 타입: {content_type_description} | 분석 항목: {total_items}개 | 생성일시: {executed_at}
        </div>
    </div>
"""

        # 프로젝트 정보 섹션 (API 데이터가 있을 때만)
        if project_title:
            title_html = f'<a href="{project_link}" target="_blank" class="project-title-link">{project_title}</a>' if project_link else project_title
            thumbnail_html = f'<img src="{project_thumbnail_url}" alt="썸네일" class="project-thumbnail">' if project_thumbnail_url else ''
            html_content += f"""
    <div class="project-info-section">
        {thumbnail_html}
        <div class="project-info-content">
            <div class="project-title">{title_html}</div>
        </div>
    </div>
"""

        # 요약에 키워드 하이라이트 적용
        highlighted_summary = cls._highlight_keywords_in_summary(summary, result.keywords)

        # 인사이트 섹션 생성
        insights_html = cls._render_insights_section(result.good_points, result.caution_points)

        html_content += f"""
    <h1>고객 의견: {content_type_description}</h1>

    <div class="summary-section">
        {highlighted_summary}
        <span class="ai-badge">ai</span> AI 기반 고객 리뷰 텍스트에서 생성됨
    </div>

    {insights_html}

    <div class="learn-more">자세히 알아보려면 선택하세요</div>

    <div class="category-grid">
"""

        # 카테고리 버튼들 생성
        for idx, category in enumerate(categories):
            sentiment = category.sentiment_type.lower() if category.sentiment_type else "neutral"
            category_display = category.display_highlight
            total_count = category.positive_count + category.negative_count

            # 아이콘 선택
            if sentiment == "positive":
                icon = "\u2713"  # ✓
            elif sentiment == "negative":
                icon = "\u2717"  # ✗
            else:
                icon = "\u25CF"  # ●

            html_content += f"""        <div class="category-item {sentiment}" onclick="toggleCategory({idx})">
            <span class="category-icon">{icon}</span>
            <span class="category-name">{category_display}</span>
            <span class="category-count">({total_count})</span>
        </div>
"""

        html_content += """    </div>

"""

        # 카테고리 상세 정보 생성
        for idx, category in enumerate(categories):
            category_name = category.name
            category_display = category.display_highlight
            # 카테고리 요약에 키워드 하이라이트 적용
            category_summary = cls._highlight_keywords_in_summary(category.summary, category.keywords)
            pos_count = category.positive_count
            neg_count = category.negative_count
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
                    content = highlight.content if highlight.content else text
                    highlight_id = f"highlight-{idx}-{h_idx}"

                    # 텍스트 길이 제한
                    display_text = text
                    if len(display_text) > 150:
                        display_text = display_text[:150] + "..."

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
        Generated by Content AI Agent | Wadiz
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
