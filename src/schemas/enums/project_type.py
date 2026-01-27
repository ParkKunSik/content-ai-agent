from enum import Enum

class ProjectType(Enum):
    """
    Defines the type of project for analysis context.
    """
    
    FUNDING = "FUNDING"
    PREORDER = "PREORDER"  
    STORE = "STORE"
    
    def __str__(self) -> str:
        return self.value