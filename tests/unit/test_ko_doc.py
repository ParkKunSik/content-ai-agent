"""
KoDoc 메타데이터 기능 테스트

JSON Schema에 KoDoc이 포함되지 않으면서 한글 설명을 추출할 수 있는지 검증합니다.
"""
import json
import pytest

from src.schemas.models.common.ko_doc import KoDoc, get_field_ko_doc
from src.schemas.models.common.category_item import CategoryItem
from src.schemas.models.common.sentiment_content import SentimentContent
from src.schemas.models.common.highlight_item import HighlightItem
from src.schemas.models.common.etc_content import EtcContent
from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult
from src.schemas.models.prompt.response.structured_analysis_refined_summary import (
    StructuredAnalysisRefinedSummary,
    RefinedCategorySummary,
)


class TestKoDoc:
    """KoDoc 메타데이터 테스트"""

    def test_ko_doc_not_in_json_schema(self):
        """JSON Schema에 KoDoc이 포함되지 않는지 확인"""
        schema = StructuredAnalysisResult.model_json_schema()
        schema_str = json.dumps(schema)

        assert "KoDoc" not in schema_str, "JSON Schema에 KoDoc이 포함되어서는 안됩니다"

    def test_no_korean_in_json_schema(self):
        """JSON Schema에 한글이 포함되지 않는지 확인 (SentimentType 제외)"""
        schema = StructuredAnalysisResult.model_json_schema()

        # SentimentType의 docstring은 아직 한글이므로 제외
        schema_copy = schema.copy()
        if "$defs" in schema_copy and "SentimentType" in schema_copy["$defs"]:
            del schema_copy["$defs"]["SentimentType"]

        schema_str = json.dumps(schema_copy)
        has_korean = any(ord(c) > 127 for c in schema_str)

        assert not has_korean, "JSON Schema에 한글이 포함되어서는 안됩니다 (SentimentType 제외)"

    def test_get_field_ko_doc_category_item(self):
        """CategoryItem 필드의 한글 설명 추출 테스트"""
        ko_doc = get_field_ko_doc(CategoryItem, "name")
        assert ko_doc is not None
        assert "카테고리명" in ko_doc

        ko_doc = get_field_ko_doc(CategoryItem, "sentiment_type")
        assert ko_doc is not None
        assert "감정 유형" in ko_doc

    def test_get_field_ko_doc_sentiment_content(self):
        """SentimentContent 필드의 한글 설명 추출 테스트"""
        ko_doc = get_field_ko_doc(SentimentContent, "score")
        assert ko_doc is not None
        assert "감정 점수" in ko_doc

    def test_get_field_ko_doc_highlight_item(self):
        """HighlightItem 필드의 한글 설명 추출 테스트"""
        ko_doc = get_field_ko_doc(HighlightItem, "keyword")
        assert ko_doc is not None
        assert "원본 키워드" in ko_doc

    def test_get_field_ko_doc_etc_content(self):
        """EtcContent 필드의 한글 설명 추출 테스트"""
        ko_doc = get_field_ko_doc(EtcContent, "reason")
        assert ko_doc is not None
        assert "사유" in ko_doc

    def test_get_field_ko_doc_structured_analysis_result(self):
        """StructuredAnalysisResult 필드의 한글 설명 추출 테스트"""
        ko_doc = get_field_ko_doc(StructuredAnalysisResult, "summary")
        assert ko_doc is not None
        assert "분석 요약" in ko_doc

    def test_get_field_ko_doc_refined_summary(self):
        """StructuredAnalysisRefinedSummary 필드의 한글 설명 추출 테스트"""
        ko_doc = get_field_ko_doc(StructuredAnalysisRefinedSummary, "categories")
        assert ko_doc is not None
        assert "카테고리" in ko_doc

    def test_get_field_ko_doc_nonexistent_field(self):
        """존재하지 않는 필드에 대한 처리 테스트"""
        ko_doc = get_field_ko_doc(CategoryItem, "nonexistent_field")
        assert ko_doc is None

    def test_english_descriptions_in_schema(self):
        """JSON Schema의 description이 영어로 작성되었는지 확인"""
        schema = StructuredAnalysisResult.model_json_schema()

        # 최상위 description 확인
        assert "Structured content analysis response model" == schema.get("description")

        # CategoryItem description 확인
        category_schema = schema["$defs"]["CategoryItem"]
        assert "Detailed analysis result model per category" == category_schema.get("description")

        # properties description 확인
        name_desc = category_schema["properties"]["name"]["description"]
        assert "Clear, descriptive category name" in name_desc
