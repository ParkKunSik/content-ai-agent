"""
LLMUsageInfo 합산 유틸리티

순차 청킹 시 여러 번의 LLM 호출 결과를 합산하여 관리합니다.
"""
from typing import List, Optional

from src.schemas.models.common.llm_usage_info import LLMUsageInfo


def merge_llm_usages(
    existing_usages: List[LLMUsageInfo],
    new_usage: LLMUsageInfo
) -> List[LLMUsageInfo]:
    """
    기존 LLM 사용 정보 리스트에 새 사용 정보를 병합합니다.

    병합 규칙:
    - step과 model이 동일하면 토큰/비용/시간을 합산
    - step이나 model이 다르면 새 항목으로 추가

    Args:
        existing_usages: 기존 LLMUsageInfo 리스트
        new_usage: 병합할 새 LLMUsageInfo

    Returns:
        병합된 LLMUsageInfo 리스트
    """
    result = []
    merged = False

    for existing in existing_usages:
        if existing.step == new_usage.step and existing.model == new_usage.model:
            # 동일한 step + model → 합산
            merged_usage = LLMUsageInfo(
                step=existing.step,
                model=existing.model,
                input_tokens=existing.input_tokens + new_usage.input_tokens,
                output_tokens=existing.output_tokens + new_usage.output_tokens,
                duration_ms=existing.duration_ms + new_usage.duration_ms,
                input_cost=_safe_add(existing.input_cost, new_usage.input_cost),
                output_cost=_safe_add(existing.output_cost, new_usage.output_cost),
                total_cost=_safe_add(existing.total_cost, new_usage.total_cost),
            )
            result.append(merged_usage)
            merged = True
        else:
            result.append(existing)

    if not merged:
        result.append(new_usage)

    return result


def merge_llm_usage_lists(
    existing_usages: List[LLMUsageInfo],
    new_usages: List[LLMUsageInfo]
) -> List[LLMUsageInfo]:
    """
    두 LLMUsageInfo 리스트를 병합합니다.

    Args:
        existing_usages: 기존 리스트
        new_usages: 병합할 리스트

    Returns:
        병합된 LLMUsageInfo 리스트
    """
    result = list(existing_usages)  # 복사
    for new_usage in new_usages:
        result = merge_llm_usages(result, new_usage)
    return result


def _safe_add(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """None 값을 안전하게 합산"""
    if a is None and b is None:
        return None
    return (a or 0.0) + (b or 0.0)
