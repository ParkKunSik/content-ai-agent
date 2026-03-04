"""
Multi-Project 배치 분석 입력 스키마

Step 1 (Structuring) 프롬프트의 입력 데이터 구조를 정의합니다.
input_schema_description 추출에 사용됩니다.
"""
from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.models.common.ko_doc import KoDoc
from src.schemas.models.prompt.analysis_content_item import AnalysisContentItem
from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult


class MultiProjectBatchItem(BaseModel):
    """
    Multi-Project 배치 분석의 단일 프로젝트 입력 모델

    Note:
        이 모델의 JSON 스키마는 LLM에게 입력 데이터 구조를 설명하는 데 사용됩니다.
        각 필드의 'description'은 LLM이 입력 데이터를 이해하는 데 도움을 줍니다.
    """

    model_config = ConfigDict(
        json_schema_extra={"description": "Single project item in multi-project batch analysis input"}
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

    content_items: Annotated[
        list[AnalysisContentItem],
        Field(description="Array of content items to analyze"),
        KoDoc("분석 대상 콘텐츠 아이템 배열")
    ]

    previous_result: Annotated[
        Optional[StructuredAnalysisResult],
        Field(default=None, description="Previous analysis result to merge with (for sequential chunking)"),
        KoDoc("병합할 이전 분석 결과 (순차 청킹용)")
    ]
