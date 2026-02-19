from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .ko_doc import KoDoc


class EtcContent(BaseModel):
    """분석에서 제외된 기타 콘텐츠 모델"""

    model_config = ConfigDict(
        json_schema_extra={"description": "Content excluded from analysis"}
    )

    id: Annotated[
        int,
        Field(description="Unique ID of the content excluded from analysis"),
        KoDoc("분석에서 제외된 콘텐츠의 고유 ID")
    ]

    reason: Annotated[
        str,
        Field(description="Specific reason for exclusion from analysis (e.g., simple greeting, meaningless repetition)"),
        KoDoc("분석에 포함하지 않은 구체적인 사유 (예: 단순 인사말, 의미 없는 반복 등)")
    ]
