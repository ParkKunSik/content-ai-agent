"""
토큰 사용량 및 비용 계산 유틸리티

LLM 모델별 토큰 사용량과 비용을 계산합니다.
"""
from typing import Callable, Awaitable, Optional, Tuple

from src.schemas.models.common.llm_usage_info import LLMUsageInfo

TOKEN_COST_CURRENCY = "USD"

# Provider별 모델 가격 테이블
MODEL_PRICING_TABLE = {
    # Google Vertex AI / Gemini 모델
    "gemini_2_5_pro": {
        "input_cost_per_million": 1.25,
        "output_cost_per_million": 5.00
    },
    "gemini_2_5_flash": {
        "input_cost_per_million": 0.10,
        "output_cost_per_million": 0.40
    },
    "gemini_3_pro_preview": {
        "input_cost_per_million": 1.50,
        "output_cost_per_million": 6.00
    },
    "gemini_3_flash_preview": {
        "input_cost_per_million": 0.15,
        "output_cost_per_million": 0.60
    },
    # OpenAI GPT-4o 시리즈
    "gpt_4o": {
        "input_cost_per_million": 2.50,
        "output_cost_per_million": 10.00
    },
    "gpt_4o_mini": {
        "input_cost_per_million": 0.15,
        "output_cost_per_million": 0.60
    },
    # OpenAI GPT-4.1 시리즈 (2025년 4월)
    "gpt_4_1": {
        "input_cost_per_million": 2.00,
        "output_cost_per_million": 8.00
    },
    "gpt_4_1_mini": {
        "input_cost_per_million": 0.40,
        "output_cost_per_million": 1.60
    },
    "gpt_4_1_nano": {
        "input_cost_per_million": 0.10,
        "output_cost_per_million": 0.40
    },
    # OpenAI GPT-5 시리즈 (2025년 8월, temperature 미지원)
    "gpt_5": {
        "input_cost_per_million": 1.25,
        "output_cost_per_million": 10.00
    },
    "gpt_5_mini": {
        "input_cost_per_million": 0.30,
        "output_cost_per_million": 1.20
    },
    "gpt_5_nano": {
        "input_cost_per_million": 0.08,
        "output_cost_per_million": 0.30
    },
    # OpenAI O-시리즈 (Reasoning, temperature 미지원, reasoning tokens 별도 과금)
    "o3": {
        "input_cost_per_million": 2.00,
        "output_cost_per_million": 8.00
    },
    "o3_mini": {
        "input_cost_per_million": 1.10,
        "output_cost_per_million": 4.40
    },
    "o4_mini": {
        "input_cost_per_million": 1.10,
        "output_cost_per_million": 4.40
    },
}

MODEL_ALIASES = {
    # Google Vertex AI / Gemini
    "gemini_2_5_pro": ["gemini-2.5-pro", "gemini-2.5-pro-preview", "gemini 2.5 pro"],
    "gemini_2_5_flash": ["gemini-2.5-flash", "gemini-2.5-flash-preview", "gemini 2.5 flash"],
    "gemini_3_pro_preview": ["gemini-3.0-pro-preview", "gemini-3-pro-preview", "gemini 3 pro (preview)", "gemini 3 pro"],
    "gemini_3_flash_preview": ["gemini-3.0-flash-preview", "gemini-3-flash-preview", "gemini 3 flash (preview)", "gemini 3 flash"],
    # OpenAI GPT-4o 시리즈
    "gpt_4o": ["gpt-4o", "gpt4o"],
    "gpt_4o_mini": ["gpt-4o-mini", "gpt4o-mini"],
    # OpenAI GPT-4.1 시리즈
    "gpt_4_1": ["gpt-4.1", "gpt4.1"],
    "gpt_4_1_mini": ["gpt-4.1-mini", "gpt4.1-mini"],
    "gpt_4_1_nano": ["gpt-4.1-nano", "gpt4.1-nano"],
    # OpenAI GPT-5 시리즈
    "gpt_5": ["gpt-5", "gpt5", "gpt-5.2", "gpt5.2"],
    "gpt_5_mini": ["gpt-5-mini", "gpt5-mini"],
    "gpt_5_nano": ["gpt-5-nano", "gpt5-nano"],
    # OpenAI O-시리즈 (Reasoning)
    "o3": ["o3"],
    "o3_mini": ["o3-mini"],
    "o4_mini": ["o4-mini"],
}


def normalize_model_name(model_name: str) -> str:
    """모델명을 정규화하여 비교 가능한 형태로 변환합니다."""
    return model_name.lower().replace(".", "").replace("-", " ").strip()


def resolve_model_pricing(model_name: str) -> dict:
    """모델명에 해당하는 가격 정보를 조회합니다."""
    normalized = normalize_model_name(model_name)
    for key, aliases in MODEL_ALIASES.items():
        if any(normalize_model_name(alias) == normalized for alias in aliases):
            return MODEL_PRICING_TABLE[key]
    print(f"  - Token cost: model '{model_name}' not found in pricing table, costs set to 0")
    return {"input_cost_per_million": 0.0, "output_cost_per_million": 0.0}


async def calculate_token_usage(
    token_counter: Callable[[list], Awaitable[int]],
    prompt: str,
    response_text: str,
    model_name: str
) -> dict:
    """
    프롬프트/응답 토큰 및 비용을 계산합니다.

    Args:
        token_counter: 토큰 수를 계산하는 비동기 함수 (예: llm_service.count_total_tokens)
        prompt: 프롬프트 텍스트
        response_text: 응답 텍스트
        model_name: 모델명

    Returns:
        토큰 사용량 및 비용 정보를 담은 딕셔너리
    """
    prompt_tokens = await token_counter([prompt])
    output_tokens = await token_counter([response_text])
    total_tokens = prompt_tokens + output_tokens

    model_costs = resolve_model_pricing(model_name)

    input_cost_per_million = model_costs["input_cost_per_million"]
    output_cost_per_million = model_costs["output_cost_per_million"]

    input_cost = round((prompt_tokens / 1_000_000) * input_cost_per_million, 6)
    output_cost = round((output_tokens / 1_000_000) * output_cost_per_million, 6)
    total_cost = round(input_cost + output_cost, 6)

    return {
        "model_name": model_name,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "input_cost_per_million": input_cost_per_million,
        "output_cost_per_million": output_cost_per_million,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "currency": TOKEN_COST_CURRENCY
    }


def print_token_usage(step_label: str, usage: dict) -> None:
    """토큰 사용량/비용을 출력합니다."""
    print(f"  - Token usage ({step_label}): input {usage['prompt_tokens']}, output {usage['output_tokens']}, total {usage['total_tokens']}")
    print(
        f"  - Token cost ({usage['currency']}): "
        f"input {usage['input_cost']}, output {usage['output_cost']}, total {usage['total_cost']}"
    )


def aggregate_token_usage(*usages: dict) -> dict:
    """여러 토큰 사용량을 합산합니다."""
    return {
        "model_name": "combined",
        "prompt_tokens": sum(u["prompt_tokens"] for u in usages),
        "output_tokens": sum(u["output_tokens"] for u in usages),
        "total_tokens": sum(u["total_tokens"] for u in usages),
        "input_cost": round(sum(u["input_cost"] for u in usages), 6),
        "output_cost": round(sum(u["output_cost"] for u in usages), 6),
        "total_cost": round(sum(u["total_cost"] for u in usages), 6),
        "currency": TOKEN_COST_CURRENCY
    }


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model_name: str
) -> Tuple[float, float, float]:
    """
    토큰 수와 모델명으로 비용을 계산합니다.

    Args:
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        model_name: 모델명

    Returns:
        Tuple[input_cost, output_cost, total_cost]
    """
    model_costs = resolve_model_pricing(model_name)

    input_cost_per_million = model_costs["input_cost_per_million"]
    output_cost_per_million = model_costs["output_cost_per_million"]

    input_cost = round((input_tokens / 1_000_000) * input_cost_per_million, 6)
    output_cost = round((output_tokens / 1_000_000) * output_cost_per_million, 6)
    total_cost = round(input_cost + output_cost, 6)

    return input_cost, output_cost, total_cost


def create_llm_usage_info(
    step: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    calculate_costs: bool = True
) -> LLMUsageInfo:
    """
    LLMUsageInfo 객체를 생성합니다.

    Args:
        step: 분석 단계 번호 (1부터 시작)
        model: 모델명
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        duration_ms: 소요 시간 (밀리초)
        calculate_costs: 비용 계산 여부 (기본값: True)

    Returns:
        LLMUsageInfo 객체
    """
    input_cost: Optional[float] = None
    output_cost: Optional[float] = None
    total_cost: Optional[float] = None

    if calculate_costs and input_tokens > 0:
        input_cost, output_cost, total_cost = calculate_cost(
            input_tokens, output_tokens, model
        )

    return LLMUsageInfo(
        step=step,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=duration_ms,
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=total_cost
    )
