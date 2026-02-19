"""Google Secret Manager Provider"""

import json
import logging
from typing import Any, Dict, Optional

from src.secrets.base import BaseSecretProvider

logger = logging.getLogger(__name__)


class GSMSecretProvider(BaseSecretProvider):
    """
    Google Secret Manager 기반 시크릿 프로바이더.
    GCP 환경에서 사용한다.
    """

    def __init__(self, project_id: str, version: str = "latest"):
        """
        GSMSecretProvider 초기화.

        Args:
            project_id: GCP 프로젝트 ID
            version: 시크릿 버전 (기본값: latest)
        """
        try:
            from google.cloud import secretmanager
        except ImportError as e:
            raise ImportError(
                "google-cloud-secret-manager package is not installed. "
                "Install it with: pip install google-cloud-secret-manager"
            ) from e

        self.project_id = project_id
        self.version = version
        self.client = secretmanager.SecretManagerServiceClient()
        logger.info(f"GSM Secret Provider initialized (project: {project_id})")

    def get_secret(self, secret_name: str) -> str:
        """
        Google Secret Manager에서 시크릿 값을 가져온다.

        Args:
            secret_name: 시크릿 이름

        Returns:
            str: 시크릿 값
        """
        name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{self.version}"

        try:
            response = self.client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            logger.debug(f"Loaded secret from GSM: {secret_name}")
            return secret_value
        except Exception as e:
            logger.error(f"Failed to load secret from GSM '{secret_name}': {e}")
            raise RuntimeError(f"GSM Secret Error: {e}") from e

    def get_secret_json(self, secret_name: str) -> Dict[str, Any]:
        """
        JSON 형식의 시크릿을 파싱하여 반환한다.

        Args:
            secret_name: 시크릿 이름

        Returns:
            Dict: 파싱된 JSON 딕셔너리
        """
        value = self.get_secret(secret_name)
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from GSM secret {secret_name}: {e}") from e
