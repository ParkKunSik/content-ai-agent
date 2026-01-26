from __future__ import annotations
from pydantic import BaseModel, Field, field_validator


class RefinedCategorySummary(BaseModel):
    """정제된 카테고리 요약 모델 (Step 2용)"""
    
    category_key: str = Field(..., description="카테고리 키 (변경되지 않음)")
    summary: str = Field(..., description="정제된 카테고리 요약 (최대 50자)")
    
    @field_validator('summary')
    @classmethod
    def validate_summary_length(cls, v: str) -> str:
        """요약 길이 제한 검증 (50자)"""
        if len(v) > 50:
            raise ValueError(f"카테고리 요약은 최대 50자까지 허용됩니다. 현재: {len(v)}자")
        return v


class DetailedAnalysisRefinedResponse(BaseModel):
    """상세 분석 정제된 응답 모델 (Step 2 출력용)"""
    
    summary: str = Field(..., description="정제된 전체 요약 (최대 300자)")
    categorys: list[RefinedCategorySummary] = Field(..., description="정제된 카테고리 요약 배열")
    
    @field_validator('summary')
    @classmethod
    def validate_summary_length(cls, v: str) -> str:
        """전체 요약 길이 제한 검증 (300자)"""
        if len(v) > 300:
            raise ValueError(f"전체 요약은 최대 300자까지 허용됩니다. 현재: {len(v)}자")
        return v