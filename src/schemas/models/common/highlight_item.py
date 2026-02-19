from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .ko_doc import KoDoc


class HighlightItem(BaseModel):
    """핵심 하이라이트 아이템 모델"""

    model_config = ConfigDict(
        json_schema_extra={"description": "Key highlight item model"}
    )

    id: Annotated[
        int,
        Field(description="Source content ID for this highlight"),
        KoDoc("이 하이라이트의 출처 콘텐츠 ID")
    ]

    keyword: Annotated[
        str,
        Field(description="Specific terms/phrases that support this highlight (MUST extract from highlight field, DO NOT generate new terms, preserve source language)"),
        KoDoc("이 하이라이트를 뒷받침하는 특정 용어/구절 (highlight 필드에서 추출 필수, 새 용어 생성 금지, 원문 언어 유지)")
    ]

    highlight: Annotated[
        str,
        Field(description="Key insight or phrase capturing the essence of the category (extract verbatim from source, preserve source language, DO NOT summarize or paraphrase)"),
        KoDoc("카테고리의 본질을 포착하는 핵심 인사이트 또는 구절 (원문에서 그대로 추출, 원문 언어 유지, 요약/의역 금지)")
    ]

    content: Annotated[
        str,
        Field(description="Full original text of the source content for this highlight (copy verbatim)"),
        KoDoc("하이라이트의 출처가 되는 원본 콘텐츠 전체 텍스트 (원문 그대로 복사)")
    ]
