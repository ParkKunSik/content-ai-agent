"""
Multi-Project 배치 정제 출력 스키마

Step 2 (Refinement) LLM 응답의 출력 데이터 구조를 정의합니다.
response_schema로 사용됩니다.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.models.common.ko_doc import KoDoc
from src.schemas.models.prompt.response.structured_analysis_refined_summary import StructuredAnalysisRefinedSummary


class MultiProjectRefinedResultItem(BaseModel):
    """
    Multi-Project 배치 정제의 단일 프로젝트 결과 모델
    """

    model_config = ConfigDict(
        json_schema_extra={"description": "Single project result in multi-project batch refinement output"}
    )

    project: Annotated[
        int,
        Field(description="Project identifier (must match input)"),
        KoDoc("프로젝트 식별자 (입력과 일치해야 함)")
    ]

    project_type: Annotated[
        str,
        Field(description="Project type (must match input)"),
        KoDoc("프로젝트 타입 (입력과 일치해야 함)")
    ]

    content_type: Annotated[
        str,
        Field(description="Content type (must match input)"),
        KoDoc("콘텐츠 타입 (입력과 일치해야 함)")
    ]

    result: Annotated[
        StructuredAnalysisRefinedSummary,
        Field(description="Refined analysis result for this project"),
        KoDoc("이 프로젝트의 정제된 분석 결과")
    ]


class MultiProjectRefinedResult(BaseModel):
    """
    Multi-Project 배치 정제의 전체 출력 모델

    Note:
        이 모델의 JSON 스키마는 Vertex AI의 'response_schema'로 전달되어
        LLM의 출력 구조와 내용을 제어하는 핵심 지침으로 사용됩니다.
    """

    model_config = ConfigDict(
        json_schema_extra={"description": "Multi-project batch refinement response model"}
    )

    results: Annotated[
        list[MultiProjectRefinedResultItem],
        Field(description="Array of refined results, one per input project in the same order"),
        KoDoc("정제된 결과 배열, 입력 프로젝트와 동일한 순서로 하나씩")
    ]
