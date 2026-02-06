from __future__ import annotations

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from src.core.config import settings

from ..common.category_summary import CategorySummary
from ..common.etc_content import EtcContent


class StructuredAnalysisResponse(BaseModel):
    """
    상세 분석 응답 모델
    
    Note:
        이 모델의 JSON 스키마는 Vertex AI의 'response_schema'로 전달되어 
        LLM의 출력 구조와 내용을 제어하는 핵심 지침으로 사용됩니다.
        각 필드의 'description'은 LLM에게 전달되는 프롬프트 역할을 하므로 명확하고 상세하게 작성해야 합니다.
    """
    
    summary: str = Field(..., description="발견된 모든 주요 주제와 인사이트를 다루는 포괄적인 분석 요약 (특수문자 Escape 필수)")
    categories: list[CategorySummary] = Field(..., description="카테고리별 상세 분석 결과 배열 (최대 20개)")
    harmful_contents: list[int] = Field(default_factory=list, description="유해한 콘텐츠 content_id 리스트 (욕설, 비난, 비방 등)")
    etc_contents: list[EtcContent] = Field(default_factory=list, description="분석에 영향을 주지 않는 기타 콘텐츠 배열")
    
    @field_validator('categories')
    @classmethod
    def validate_categorys_count(cls, v: list[CategorySummary]) -> list[CategorySummary]:
        if not settings.STRICT_VALIDATION:
            return v

        """카테고리 개수 제한 검증 (최대 20개)"""
        if len(v) > 20:
            raise ValueError(f"카테고리는 최대 20개까지만 허용됩니다. 현재: {len(v)}개")
        return v
    
    @field_validator('categories')
    @classmethod
    def validate_unique_category_keys(cls, v: list[CategorySummary]) -> list[CategorySummary]:
        if not settings.STRICT_VALIDATION:
            return v

        """카테고리 키 중복 검증"""
        category_keys = [cat.category_key for cat in v]
        if len(category_keys) != len(set(category_keys)):
            duplicates = [key for key in category_keys if category_keys.count(key) > 1]
            raise ValueError(f"중복된 category_key가 있습니다: {duplicates}")
        return v
    
    @field_validator('harmful_contents', 'etc_contents', 'categories')
    @classmethod
    def validate_no_content_id_duplication(cls, v, info: ValidationInfo) -> list:
        if not settings.STRICT_VALIDATION:
            return v

        """content_id 중복 방지 검증"""
        # data는 현재까지 검증이 완료된 다른 필드들의 딕셔너리 (V2 스타일)
        data = info.data
        used_content_ids: set[int] = set()
        
        # field_name에 따라 분기 처리
        field_name = info.field_name
        
        # 1. 이미 데이터에 있는 content_id 수집 (이전 필드들)
        if 'harmful_contents' in data and field_name != 'harmful_contents':
            used_content_ids.update(data['harmful_contents'])
        
        if 'etc_contents' in data and field_name != 'etc_contents':
            for etc_content in data['etc_contents']:
                used_content_ids.add(etc_content.id)
        
        if 'categories' in data and field_name != 'categories':
             for category in data['categories']:
                for content in category.positive_contents + category.negative_contents:
                    used_content_ids.add(content.id)

        # 2. 현재 검증 중인 필드(v) 내에서 중복 및 기존 데이터와의 중복 검사
        if field_name == 'harmful_contents':
            for content_id in v:
                if content_id in used_content_ids:
                    raise ValueError(
                        f"content_id {content_id}이 중복되었습니다. 현재 필드: harmful_contents"
                    )
                used_content_ids.add(content_id)

        elif field_name == 'etc_contents':
            for etc_content in v:
                if etc_content.id in used_content_ids:
                    raise ValueError(
                        f"content_id {etc_content.id}이 중복되었습니다. 현재 필드: etc_contents"
                    )
                used_content_ids.add(etc_content.id)

        elif field_name == 'categories':
            for category in v:
                for content in category.positive_contents:
                    if content.id in used_content_ids:
                        raise ValueError(
                            f"content_id {content.id}이 중복되었습니다. "
                            f"현재 필드: categories.{category.category_key}.positive_contents"
                        )
                    used_content_ids.add(content.id)

                for content in category.negative_contents:
                    if content.id in used_content_ids:
                        raise ValueError(
                            f"content_id {content.id}이 중복되었습니다. "
                            f"현재 필드: categories.{category.category_key}.negative_contents"
                        )
                    used_content_ids.add(content.id)

                # highlights는 참조용이므로 중복 검사 제외
        
        return v