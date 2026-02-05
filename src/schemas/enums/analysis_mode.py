from enum import Enum

from .persona_type import PersonaType

class AnalysisMode(str, Enum):
    """
    External interface for choosing the analysis persona.
    """
    REVIEW_BOT = (PersonaType.CUSTOMER_FACING_SMART_BOT)
    DATA_ANALYST = (PersonaType.PRO_DATA_ANALYST)

    def __init__(self, persona_type: PersonaType):
        self._value_ = self.name
        self.persona_type = persona_type