from enum import Enum

class ProjectType(Enum):
    """
    Defines the type of project for analysis context.
    - ES 데이터에는 Funding/Preorder 구분이 없고 Store 데이터는 없는 상태
    """

    FUNDING_AND_PREORDER = "FUNDING_AND_PREORDER"
    FUNDING = "FUNDING"
    PREORDER = "PREORDER"  
    STORE = "STORE"
    GENERAL = "GENERAL"
    
    def __str__(self) -> str:
        return self.value