import logging
from google.cloud import storage
from src.core.config import settings
from src.loaders.base import BaseContentLoader

logger = logging.getLogger(__name__)

class GCSLoader(BaseContentLoader):
    """Loader for Google Cloud Storage (gs://)."""
    
    def __init__(self):
        try:
            self.client = storage.Client(project=settings.GCP_PROJECT_ID)
        except Exception as e:
            logger.error(f"Failed to initialize GCS Client: {e}")
            self.client = None

    def load_content(self, uri: str) -> str:
        if not self.client:
            raise RuntimeError("GCS Client is not initialized.")
            
        if not uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {uri}")

        # Parse bucket and blob name
        # gs://bucket-name/path/to/file.txt
        parts = uri[5:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid GCS URI format: {uri}")
            
        bucket_name, blob_name = parts
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            content = blob.download_as_text(encoding="utf-8")
            logger.info(f"Loaded content from GCS: {uri}")
            return content
        except Exception as e:
            logger.error(f"Failed to load from GCS {uri}: {e}")
            raise RuntimeError(f"GCS Load Error: {e}") from e

    def get_file_size(self, uri: str) -> int:
        if not self.client:
            raise RuntimeError("GCS Client is not initialized.")
            
        if not uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {uri}")

        # Parse bucket and blob name
        parts = uri[5:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid GCS URI format: {uri}")
            
        bucket_name, blob_name = parts
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.reload()  # Load blob metadata
            size = blob.size
            logger.info(f"Got file size from GCS: {uri} ({size} bytes)")
            return size
        except Exception as e:
            logger.error(f"Failed to get file size from GCS {uri}: {e}")
            raise RuntimeError(f"GCS File Size Error: {e}") from e