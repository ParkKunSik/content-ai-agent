from pydantic import BaseModel, Field, computed_field
from typing import Optional


class LLMUsageInfo(BaseModel):
    """LLM 호출별 사용 정보"""

    step: int = Field(
        description="분석 단계 번호 (1부터 시작)"
    )
    model: str = Field(
        description="사용된 LLM 모델명 (예: 'gemini-2.0-flash')"
    )
    input_tokens: int = Field(
        default=0,
        description="입력 토큰 수"
    )
    output_tokens: int = Field(
        default=0,
        description="출력 토큰 수"
    )
    duration_ms: int = Field(
        default=0,
        description="소요 시간 (밀리초)"
    )
    # 비용 관련 필드 (Optional - 계산되지 않을 수 있음)
    input_cost: Optional[float] = Field(
        default=None,
        description="입력 토큰 비용 (USD)"
    )
    output_cost: Optional[float] = Field(
        default=None,
        description="출력 토큰 비용 (USD)"
    )
    total_cost: Optional[float] = Field(
        default=None,
        description="총 비용 (USD)"
    )

    @computed_field
    @property
    def total_tokens(self) -> int:
        """총 토큰 수"""
        return self.input_tokens + self.output_tokens
