from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.models.common.ko_doc import KoDoc


class AnalysisContentItem(BaseModel):
    """
    상세 분석 프롬프트에 주입할 콘텐츠 아이템 모델

    Note:
        이 모델의 JSON 스키마는 LLM에게 입력 데이터 구조를 설명하는 데 사용됩니다.
        각 필드의 'description'은 LLM이 입력 데이터를 이해하는 데 도움을 줍니다.
    """

    model_config = ConfigDict(
        json_schema_extra={"description": "Content item for analysis input"}
    )

    id: Annotated[
        int,
        Field(description="Unique content identifier for tracking in analysis results"),
        KoDoc("분석 결과 추적을 위한 콘텐츠 고유 식별자")
    ]

    content: Annotated[
        str,
        Field(description="Text content to analyze"),
        KoDoc("분석 대상 콘텐츠 텍스트")
    ]

    has_image: Annotated[
        Optional[bool],
        Field(default=None, description="Image attachment indicator (only present when true, prioritize for highlight selection)"),
        KoDoc("이미지 첨부 여부 (true인 경우에만 포함, 하이라이트 선택 시 우선순위 부여)")
    ]
