"""
Multi-Project 배치 정제 입력 스키마

Step 2 (Refinement) 프롬프트의 입력 데이터 구조를 정의합니다.
input_schema_description 추출에 사용됩니다.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.models.common.ko_doc import KoDoc
from src.schemas.models.prompt.structured_analysis_summary import StructuredAnalysisSummary


class MultiProjectSummaryItem(BaseModel):
    """
    Multi-Project 배치 정제의 단일 프로젝트 입력 모델

    Note:
        이 모델의 JSON 스키마는 LLM에게 입력 데이터 구조를 설명하는 데 사용됩니다.
        각 필드의 'description'은 LLM이 입력 데이터를 이해하는 데 도움을 줍니다.
    """

    model_config = ConfigDict(
        json_schema_extra={"description": "Single project item in multi-project batch refinement input"}
    )

    project: Annotated[
        int,
        Field(description="Project identifier"),
        KoDoc("프로젝트 식별자")
    ]

    project_type: Annotated[
        str,
        Field(description="Project type (e.g., 'funding', 'store')"),
        KoDoc("프로젝트 타입 (예: 'funding', 'store')")
    ]

    content_type: Annotated[
        str,
        Field(description="Content type (e.g., 'REVIEW', 'SUPPORT')"),
        KoDoc("콘텐츠 타입 (예: 'REVIEW', 'SUPPORT')")
    ]

    analysis_data: Annotated[
        StructuredAnalysisSummary,
        Field(description="Analysis data to refine (summary, keywords, categories, insights)"),
        KoDoc("정제할 분석 데이터 (요약, 키워드, 카테고리, 인사이트)")
    ]
