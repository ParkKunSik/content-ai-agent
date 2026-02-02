from enum import Enum

from .persona_type import PersonaType

class AnalysisMode(str, Enum):
    """
    External interface for choosing the analysis persona.
    """
    SELLER_ASSISTANT = (PersonaType.CUSTOMER_FACING_ANALYST)
    DATA_ANALYST = (PersonaType.PRO_DATA_ANALYST)
    REVIEW_BOT = (PersonaType.CUSTOMER_FACING_SMART_BOT)

    def __init__(self, persona_type: PersonaType):
        self._value_ = self.name
        self.persona_type = persona_type