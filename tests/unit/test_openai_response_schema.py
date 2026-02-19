"""
OpenAI Response Schema 출력 테스트

OpenAI responses.parse API에 text_format으로 전달되는 Pydantic 모델의
JSON Schema 형태를 확인하기 위한 테스트입니다.
"""

import json
import pytest


class TestOpenAIResponseSchema:
    """OpenAI response schema 출력 테스트"""

    def test_structured_analysis_result_schema(self):
        """StructuredAnalysisResult의 JSON Schema 출력"""
        from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult

        schema = StructuredAnalysisResult.model_json_schema()

        print("\n" + "=" * 80)
        print("StructuredAnalysisResult JSON Schema")
        print("=" * 80)
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        print("=" * 80)

        # 기본 구조 검증
        assert "properties" in schema
        assert "summary" in schema["properties"]
        assert "categories" in schema["properties"]
        assert "harmful_contents" in schema["properties"]
        assert "etc_contents" in schema["properties"]

    def test_structured_analysis_refined_summary_schema(self):
        """StructuredAnalysisRefinedSummary의 JSON Schema 출력"""
        from src.schemas.models.prompt.response.structured_analysis_refined_summary import (
            StructuredAnalysisRefinedSummary,
        )

        schema = StructuredAnalysisRefinedSummary.model_json_schema()

        print("\n" + "=" * 80)
        print("StructuredAnalysisRefinedSummary JSON Schema")
        print("=" * 80)
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        print("=" * 80)

        # 기본 구조 검증
        assert "properties" in schema
        assert "summary" in schema["properties"]
        assert "categories" in schema["properties"]

    def test_refined_category_summary_schema(self):
        """RefinedCategorySummary의 JSON Schema 출력"""
        from src.schemas.models.prompt.response.structured_analysis_refined_summary import (
            RefinedCategorySummary,
        )

        schema = RefinedCategorySummary.model_json_schema()

        print("\n" + "=" * 80)
        print("RefinedCategorySummary JSON Schema")
        print("=" * 80)
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        print("=" * 80)

        # 기본 구조 검증
        assert "properties" in schema
        assert "key" in schema["properties"]
        assert "summary" in schema["properties"]

    def test_schema_descriptions_present(self):
        """스키마의 description 필드가 올바르게 포함되어 있는지 확인"""
        from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult
        from src.schemas.models.prompt.response.structured_analysis_refined_summary import (
            StructuredAnalysisRefinedSummary,
        )

        # StructuredAnalysisResult descriptions
        result_schema = StructuredAnalysisResult.model_json_schema()
        assert "description" in result_schema["properties"]["summary"]
        assert "description" in result_schema["properties"]["categories"]

        # StructuredAnalysisRefinedSummary descriptions
        refined_schema = StructuredAnalysisRefinedSummary.model_json_schema()
        assert "description" in refined_schema["properties"]["summary"]
        assert "description" in refined_schema["properties"]["categories"]

        print("\n" + "=" * 80)
        print("Schema Descriptions Verification")
        print("=" * 80)
        print(f"StructuredAnalysisResult.summary: {result_schema['properties']['summary']['description']}")
        print(f"StructuredAnalysisRefinedSummary.summary: {refined_schema['properties']['summary']['description']}")
        print("=" * 80)

    def test_nested_schema_definitions(self):
        """중첩된 스키마 정의($defs) 확인"""
        from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult

        schema = StructuredAnalysisResult.model_json_schema()

        print("\n" + "=" * 80)
        print("Nested Schema Definitions ($defs)")
        print("=" * 80)

        if "$defs" in schema:
            for def_name, def_schema in schema["$defs"].items():
                print(f"\n--- {def_name} ---")
                print(json.dumps(def_schema, indent=2, ensure_ascii=False))
        else:
            print("No $defs found in schema")

        print("=" * 80)

        # $defs 존재 확인 (중첩 모델이 있으므로)
        assert "$defs" in schema
        assert "CategoryItem" in schema["$defs"]
