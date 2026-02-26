"""AWS Secrets Manager Provider"""

import json
import logging
from typing import Any, Dict

from src.core.config.secrets.base import SecretProvider

logger = logging.getLogger(__name__)


class AWSSecretProvider(SecretProvider):
    """AWS Secrets Manager에서 설정을 가져온다."""

    def __init__(self, region: str = "ap-northeast-2"):
        self.region = region
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("secretsmanager", region_name=self.region)
        return self._client

    def fetch_secrets(self, secret_id: str) -> Dict[str, Any]:
        """
        AWS Secrets Manager에서 설정을 가져온다.

        Secret 이름 형식: {env}/content-ai/config
        예: dev/content-ai/config, prod/content-ai/config
        """
        client = self._get_client()

        logger.info(f"Fetching secrets from AWS: {secret_id}")

        try:
            response = client.get_secret_value(SecretId=secret_id)
            return json.loads(response["SecretString"])
        except Exception as e:
            logger.error(f"Failed to fetch secrets from AWS: {e}")
            raise
