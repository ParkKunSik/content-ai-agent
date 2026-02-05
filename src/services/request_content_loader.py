import logging
from typing import List, Optional

from src.core.config import settings
from src.loaders.base import BaseContentLoader
from src.loaders.gcs_loader import GCSLoader
from src.loaders.local_file_loader import LocalFileLoader
from src.schemas.models.api.file_size_validation_response import FileSizeValidationResponse
from src.schemas.models.api.file_validation_result import FileValidationResult

logger = logging.getLogger(__name__)

# Constants for file size validation  
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

class RequestContentLoader:
    """
    Service to handle bulk loading of content from analysis requests.
    Delegates to specific loaders based on source type (GCS vs Local).
    """
    def __init__(self):
        self.gcs_loader = GCSLoader()
        self.local_loader = LocalFileLoader()
    
    def _get_loader(self, source: str) -> Optional[BaseContentLoader]:
        """
        Determines the correct loader based on source prefix and environment.
        
        Args:
            source: Source URI or path
            
        Returns:
            BaseContentLoader: Appropriate loader or None if invalid
        """
        # Case 1: Google Cloud Storage
        if source.startswith("gs://"):
            return self.gcs_loader
        
        # Case 2: Local File System (only in local environment)
        if settings.ENV == "local":
            return self.local_loader
        
        # Case 3: Invalid Scenario
        return None

    def load_single(self, source: str) -> str:
        """
        Loads content from a single source using the appropriate loader.
        """
        loader = self._get_loader(source)
        if loader is None:
            raise ValueError(
                f"Invalid content source for environment '{settings.ENV}': {source}. "
                "Only 'gs://' URIs are supported in production environments."
            )
        
        return loader.load_content(source)

    def load_all(self, sources: List[str]) -> List[str]:
        """Loads content from multiple sources in bulk."""
        results = []
        for src in sources:
            try:
                content = self.load_single(src)
                if content:
                    results.append(content)
            except Exception as e:
                logger.warning(f"Skipping source '{src}' due to error: {e}")
                # We skip failed items to allow partial processing of the request
                continue
        return results

    def get_single_file_size(self, source: str) -> int:
        """Gets the file size for a single source using the appropriate loader."""
        loader = self._get_loader(source)
        if loader is None:
            raise ValueError(
                f"Invalid content source for environment '{settings.ENV}': {source}. "
                "Only 'gs://' URIs are supported in production environments."
            )
        
        return loader.get_file_size(source)

    def validate_file_sizes(self, sources: List[str]) -> FileSizeValidationResponse:
        """
        Validates file sizes for multiple sources.
        
        Args:
            sources: List of file sources (GCS URIs or local paths)
            
        Returns:
            FileSizeValidationResponse: Validation results for each file
        """
        results = []
        
        for source in sources:
            try:
                file_size = self.get_single_file_size(source)
                
                results.append(FileValidationResult(
                    source=source,
                    is_valid=file_size <= MAX_FILE_SIZE_BYTES,
                    size_bytes=file_size
                ))
                
            except Exception as e:
                logger.error(f"Failed to validate file size for {source}: {e}")
                results.append(FileValidationResult(
                    source=source,
                    is_valid=False,
                    size_bytes=0
                ))
        
        # Check if all files are valid
        is_valid = all(result.is_valid for result in results)
        
        return FileSizeValidationResponse(
            is_valid=is_valid,
            max_size_bytes=MAX_FILE_SIZE_BYTES,
            results=results
        )