"""AWS S3 Content Loader"""

import logging
from typing import Optional

from src.loaders.base import BaseContentLoader

logger = logging.getLogger(__name__)


class S3Loader(BaseContentLoader):
    """Loader for AWS S3 (s3://)."""

    def __init__(self, region_name: Optional[str] = None):
        """
        S3Loader 초기화.

        Args:
            region_name: AWS 리전 (None이면 기본 리전 사용)
        """
        try:
            import boto3
        except ImportError as e:
            raise ImportError(
                "boto3 package is not installed. "
                "Install it with: pip install boto3"
            ) from e

        try:
            self.client = boto3.client("s3", region_name=region_name)
            self.region_name = region_name
            logger.info(f"S3 Client initialized (region: {region_name or 'default'})")
        except Exception as e:
            logger.error(f"Failed to initialize S3 Client: {e}")
            self.client = None

    def load_content(self, uri: str) -> str:
        """
        S3에서 콘텐츠를 로드한다.

        Args:
            uri: S3 URI (s3://bucket-name/path/to/file.txt)

        Returns:
            str: 파일 콘텐츠
        """
        if not self.client:
            raise RuntimeError("S3 Client is not initialized.")

        bucket_name, key = self._parse_s3_uri(uri)

        try:
            response = self.client.get_object(Bucket=bucket_name, Key=key)
            content = response["Body"].read().decode("utf-8")
            logger.info(f"Loaded content from S3: {uri}")
            return content
        except Exception as e:
            logger.error(f"Failed to load from S3 {uri}: {e}")
            raise RuntimeError(f"S3 Load Error: {e}") from e

    def get_file_size(self, uri: str) -> int:
        """
        S3 파일의 크기를 반환한다.

        Args:
            uri: S3 URI (s3://bucket-name/path/to/file.txt)

        Returns:
            int: 파일 크기 (bytes)
        """
        if not self.client:
            raise RuntimeError("S3 Client is not initialized.")

        bucket_name, key = self._parse_s3_uri(uri)

        try:
            response = self.client.head_object(Bucket=bucket_name, Key=key)
            size = response["ContentLength"]
            logger.info(f"Got file size from S3: {uri} ({size} bytes)")
            return size
        except Exception as e:
            logger.error(f"Failed to get file size from S3 {uri}: {e}")
            raise RuntimeError(f"S3 File Size Error: {e}") from e

    def _parse_s3_uri(self, uri: str) -> tuple:
        """
        S3 URI를 파싱하여 bucket_name과 key를 반환한다.

        Args:
            uri: S3 URI (s3://bucket-name/path/to/file.txt)

        Returns:
            tuple: (bucket_name, key)
        """
        if not uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {uri}")

        # s3://bucket-name/path/to/file.txt
        parts = uri[5:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {uri}")

        return parts[0], parts[1]
