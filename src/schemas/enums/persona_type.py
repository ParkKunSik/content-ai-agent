from enum import Enum
from typing import Callable, Any, Optional

from src.core.config import settings
from src.utils.prompt_renderer import PromptRenderer

class PersonaType(Enum):
    """
    Defines model roles and their configuration logic.
    """
    
    # 1. Utility Models
    COMMON_TOKEN_COUNTER = (lambda s: s.VERTEX_AI_MODEL_PRO, None)
    
    # 2. Logic Models
    SUMMARY_DATA_ANALYST = (lambda s: s.VERTEX_AI_MODEL_FLASH, "Precise Content Summarizer")
    
    # 3. Persona Models
    CUSTOMER_FACING_ANALYST = (lambda s: s.VERTEX_AI_MODEL_PRO, "Customer-Facing Data Analyst")
    PRO_DATA_ANALYST = (lambda s: s.VERTEX_AI_MODEL_PRO, "Precise Data Analyst")
    CUSTOMER_FACING_SMART_BOT = (lambda s: s.VERTEX_AI_MODEL_FLASH, "Smart AI Review Analyst")

    def __init__(self, model_name_getter: Callable[[Any], str], role_description: Optional[str]):
        self.model_name_getter = model_name_getter
        self.role_description = role_description

    def get_instruction(self, pm: PromptRenderer) -> Optional[str]:
        if self.role_description is None:
            return None
        return pm.render(
            f"system/{settings.SYSTEM_INSTRUCTION_VERSION}/{self.name}.j2", 
            agent_id=settings.INTERNAL_AGENT_ID, 
            role=self.role_description
        )