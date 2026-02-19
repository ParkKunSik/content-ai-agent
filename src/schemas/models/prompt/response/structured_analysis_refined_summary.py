from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.config import settings
from src.schemas.models.common.ko_doc import KoDoc


class RefinedCategorySummary(BaseModel):
    """정제된 카테고리 요약 모델"""

    model_config = ConfigDict(
        json_schema_extra={"description": "Refined category summary model"}
    )

    key: Annotated[
        str,
        Field(description="Category unique key (keep exactly same as input data key, no case changes)"),
        KoDoc("카테고리 고유 키 (입력 데이터의 키값과 정확히 동일하게 유지, 대소문자 변경 금지)")
    ]

    summary: Annotated[
        str,
        Field(description="Refined category summary (write as complete sentences, DO NOT use abbreviated style, adhere to character limit rules)"),
        KoDoc("정제된 카테고리 요약 (완전한 문장으로 작성, 줄임말 스타일 금지, 글자수 제한 규칙 준수)")
    ]

    @field_validator('summary')
    @classmethod
    def validate_summary_length(cls, v: str) -> str:
        if not settings.STRICT_VALIDATION:
            return v

        """요약 길이 제한 검증 (설정값 기반)"""
        max_chars = settings.MAX_CATEGORY_SUMMARY_CHARS
        if len(v) > max_chars:
            raise ValueError(f"카테고리 요약은 최대 {max_chars}자까지 허용됩니다. 현재: {len(v)}자")
        return v


class StructuredAnalysisRefinedSummary(BaseModel):
    """
    상세 분석 정제된 응답 모델

    Note:
        이 모델의 JSON 스키마는 Vertex AI의 'response_schema'로 전달되어
        LLM의 출력 구조와 내용을 제어하는 핵심 지침으로 사용됩니다.
        각 필드의 'description'은 LLM에게 전달되는 프롬프트 역할을 하므로 명확하고 상세하게 작성해야 합니다.

        중요: 'StructuredAnalysisSummary'(입력 데이터 모델)와 필드 구조가 동일하더라도,
        출력 단계에서 LLM에게 전달할 전용 지침을 'description'에 포함해야 하므로
        반드시 분리된 상태를 유지해야 합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={"description": "Refined structured analysis response model"}
    )

    summary: Annotated[
        str,
        Field(description="Refined overall analysis summary (write as complete sentences, DO NOT use abbreviated style, adhere to character limit rules)"),
        KoDoc("정제된 전체 분석 요약 (완전한 문장으로 작성, 줄임말 스타일 금지, 글자수 제한 규칙 준수)")
    ]

    categories: Annotated[
        list[RefinedCategorySummary],
        Field(description="Array of refined category summaries (must include all input categories)"),
        KoDoc("정제된 카테고리 요약 배열 (입력된 모든 카테고리 포함 필수)")
    ]

    @field_validator('summary')
    @classmethod
    def validate_summary_length(cls, v: str) -> str:
        if not settings.STRICT_VALIDATION:
            return v

        """전체 요약 길이 제한 검증 (설정값 기반)"""
        max_chars = settings.MAX_MAIN_SUMMARY_CHARS
        if len(v) > max_chars:
            raise ValueError(f"전체 요약은 최대 {max_chars}자까지 허용됩니다. 현재: {len(v)}자")
        return v
