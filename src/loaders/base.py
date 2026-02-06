from abc import ABC, abstractmethod


class BaseContentLoader(ABC):
    """Abstract base class for individual content loaders."""
    
    @abstractmethod
    def load_content(self, uri: str) -> str:
        """Loads text content from the given URI/Path."""
        pass
    
    @abstractmethod
    def get_file_size(self, uri: str) -> int:
        """Gets the file size in bytes from the given URI/Path."""
        pass