import logging
import os
from src.loaders.base import BaseContentLoader

logger = logging.getLogger(__name__)

class LocalFileLoader(BaseContentLoader):
    """Loader for local file system (Development only)."""

    def load_content(self, path: str) -> str:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Local file not found: {path}")
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info(f"Loaded content from local file: {path}")
            return content
        except Exception as e:
            logger.error(f"Failed to read local file {path}: {e}")
            raise RuntimeError(f"Local File Load Error: {e}") from e

    def get_file_size(self, path: str) -> int:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Local file not found: {path}")
        
        try:
            size = os.path.getsize(path)
            logger.info(f"Got file size from local file: {path} ({size} bytes)")
            return size
        except Exception as e:
            logger.error(f"Failed to get file size from local file {path}: {e}")
            raise RuntimeError(f"Local File Size Error: {e}") from e