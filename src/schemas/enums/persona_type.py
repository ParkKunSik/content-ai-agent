from enum import Enum
from typing import Any, Callable, Optional

from src.core.config import settings
from src.utils.prompt_renderer import PromptRenderer


class PersonaType(Enum):
    """
    Defines model roles, their configuration logic, and generation parameters.

    Attributes:
        vertexai_model_name_getter: A function that retrieves the Vertex AI model name from settings.
        openai_model_name_getter: A function that retrieves the OpenAI model name from settings.
        role_description: A human-readable description of the persona's role.
        vertexai_temperature: Temperature for Vertex AI (Gemini) models.
        openai_temperature: Temperature for OpenAI (GPT) models.
            - 0.0: Deterministic. Best for technical tasks like token counting.
            - 0.1 - 0.3: Focused and precise. Ideal for data analysis, JSON structuring, and factual summaries.
            - 0.4 - 0.6: Balanced. Good for general conversational tasks.
            - 0.7 - 1.0: Creative and diverse. Best for brainstorming or varied insight generation.

        Note: OpenAI models tend to interpret temperature more conservatively than Vertex AI,
              so OpenAI temperatures are set slightly lower for equivalent behavior.
    """

    # 1. Utility Models
    # (vertexai_model_getter, openai_model_getter, role_description, vertexai_temp, openai_temp)
    COMMON_TOKEN_COUNTER = (lambda s: s.VERTEX_AI_MODEL_PRO, lambda s: s.OPENAI_MODEL_PRO, None, 0.0, 0.0)

    # 2. Persona Models
    # CUSTOMER_FACING_ANALYST: Creative insight (Vertex 0.7 → OpenAI 0.5)
    CUSTOMER_FACING_ANALYST = (lambda s: s.VERTEX_AI_MODEL_PRO, lambda s: s.OPENAI_MODEL_PRO, "Customer-Facing Data Analyst", 0.7, 0.5)
    # PRO_DATA_ANALYST: Precise analysis (Vertex 0.1 → OpenAI 0.0)
    PRO_DATA_ANALYST = (lambda s: s.VERTEX_AI_MODEL_PRO, lambda s: s.OPENAI_MODEL_PRO, "Precise Data Analyst", 0.1, 0.0)
    # CUSTOMER_FACING_SMART_BOT: Refined summary (Vertex 0.3 → OpenAI 0.2)
    CUSTOMER_FACING_SMART_BOT = (lambda s: s.VERTEX_AI_MODEL_FLASH, lambda s: s.OPENAI_MODEL_FLASH, "Smart AI Review Analyst", 0.3, 0.2)

    def __init__(
        self,
        vertexai_model_name_getter: Callable[[Any], str],
        openai_model_name_getter: Callable[[Any], str],
        role_description: Optional[str],
        vertexai_temperature: float,
        openai_temperature: float
    ):
        self.vertexai_model_name_getter = vertexai_model_name_getter
        self.openai_model_name_getter = openai_model_name_getter
        self.role_description = role_description
        self.vertexai_temperature = vertexai_temperature
        self.openai_temperature = openai_temperature

    @property
    def model_name_getter(self) -> Callable[[Any], str]:
        """하위 호환성을 위한 프로퍼티. LLM_PROVIDER에 따라 적절한 getter 반환."""
        return self.get_model_name_getter()

    def get_model_name_getter(self) -> Callable[[Any], str]:
        """현재 LLM_PROVIDER 설정에 따라 적절한 model_name_getter를 반환한다."""
        provider = settings.LLM_PROVIDER.upper()
        if provider == "OPENAI":
            return self.openai_model_name_getter
        else:
            # VERTEX_AI 또는 기타 → Vertex AI 사용
            return self.vertexai_model_name_getter

    def get_model_name(self) -> str:
        """현재 LLM_PROVIDER 설정에 따라 적절한 모델명을 반환한다."""
        return self.get_model_name_getter()(settings)

    @property
    def temperature(self) -> float:
        """하위 호환성을 위한 프로퍼티. get_temperature()와 동일."""
        return self.get_temperature()

    def get_temperature(self) -> float:
        """현재 LLM_PROVIDER 설정에 따라 적절한 temperature를 반환한다."""
        provider = settings.LLM_PROVIDER.upper()
        if provider == "OPENAI":
            return self.openai_temperature
        else:
            # VERTEX_AI 또는 기타 → Vertex AI 사용
            return self.vertexai_temperature

    def get_instruction(self, pm: PromptRenderer, provider: str = None) -> Optional[str]:
        """
        Provider에 따라 최적화된 System Instruction을 반환한다.

        Args:
            pm: PromptRenderer 인스턴스
            provider: LLM Provider (OPENAI, VERTEX_AI). None이면 settings에서 가져옴.

        Returns:
            렌더링된 System Instruction 문자열. role_description이 없으면 None.
        """
        if self.role_description is None:
            return None

        # Provider 결정 (파라미터 없으면 settings에서)
        if provider is None:
            provider = settings.LLM_PROVIDER.upper()

        # 소문자 변환: PRO_DATA_ANALYST → pro_data_analyst
        template_name = self.name.lower()

        # Provider별 경로: system/openai/pro_data_analyst.j2
        provider_path = provider.lower()  # OPENAI → openai, VERTEX_AI → vertex_ai

        return pm.render(
            f"system/{provider_path}/{template_name}.j2",
            agent_id=settings.INTERNAL_AGENT_ID,
            role=self.role_description
        )