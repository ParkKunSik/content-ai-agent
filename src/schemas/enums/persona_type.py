from enum import Enum
from typing import Callable, Any, Optional

from src.core.config import settings
from src.utils.prompt_renderer import PromptRenderer

class PersonaType(Enum):
    """
    Defines model roles, their configuration logic, and generation parameters.
    
    Attributes:
        model_name_getter: A function that retrieves the model name from settings.
        role_description: A human-readable description of the persona's role.
        temperature: Controls the degree of randomness in token generation.
            - 0.0: Deterministic. Best for technical tasks like token counting.
            - 0.1 - 0.3: Focused and precise. Ideal for data analysis, JSON structuring, and factual summaries.
            - 0.4 - 0.6: Balanced. Good for general conversational tasks.
            - 0.7 - 1.0: Creative and diverse. Best for brainstorming or varied insight generation.
    """
    
    # 1. Utility Models
    COMMON_TOKEN_COUNTER = (lambda s: s.VERTEX_AI_MODEL_PRO, None, 0.0)
    
    # 2. Logic Models
    # SUMMARY_DATA_ANALYST: 0.3 (Consistent summary)
    SUMMARY_DATA_ANALYST = (lambda s: s.VERTEX_AI_MODEL_FLASH, "Precise Content Summarizer", 0.3)
    
    # 3. Persona Models
    # CUSTOMER_FACING_ANALYST: 0.7 (Creative insight)
    CUSTOMER_FACING_ANALYST = (lambda s: s.VERTEX_AI_MODEL_PRO, "Customer-Facing Data Analyst", 0.7)
    # PRO_DATA_ANALYST: 0.1 (Precise analysis)
    PRO_DATA_ANALYST = (lambda s: s.VERTEX_AI_MODEL_PRO, "Precise Data Analyst", 0.1)
    # CUSTOMER_FACING_SMART_BOT: 0.3 (Refined summary)
    CUSTOMER_FACING_SMART_BOT = (lambda s: s.VERTEX_AI_MODEL_FLASH, "Smart AI Review Analyst", 0.3)

    def __init__(self, model_name_getter: Callable[[Any], str], role_description: Optional[str], temperature: float):
        self.model_name_getter = model_name_getter
        self.role_description = role_description
        self.temperature = temperature

    def get_instruction(self, pm: PromptRenderer) -> Optional[str]:
        if self.role_description is None:
            return None
        return pm.render(
            f"system/{settings.SYSTEM_INSTRUCTION_VERSION}/{self.name}.j2", 
            agent_id=settings.INTERNAL_AGENT_ID, 
            role=self.role_description
        )