"""GCP Secret Manager Provider"""

import json
import logging
from typing import Any, Dict

from src.core.config.secrets.base import SecretProvider

logger = logging.getLogger(__name__)


class GCPSecretProvider(SecretProvider):
    """GCP Secret Manager에서 설정을 가져온다."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import secretmanager
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def fetch_secrets(self, secret_id: str) -> Dict[str, Any]:
        """
        GCP Secret Manager에서 설정을 가져온다.

        Secret 이름 형식: {env}-content-ai-config
        예: dev-content-ai-config, prod-content-ai-config
        """
        client = self._get_client()
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"

        logger.info(f"Fetching secrets from GCP: {secret_id}")

        try:
            response = client.access_secret_version(request={"name": name})
            return json.loads(response.payload.data.decode("UTF-8"))
        except Exception as e:
            logger.error(f"Failed to fetch secrets from GCP: {e}")
            raise
