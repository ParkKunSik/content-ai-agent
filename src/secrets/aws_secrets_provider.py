"""AWS Secrets Manager Provider"""

import json
import logging
from typing import Any, Dict, Optional

from src.secrets.base import BaseSecretProvider

logger = logging.getLogger(__name__)


class AWSSecretsProvider(BaseSecretProvider):
    """
    AWS Secrets Manager 기반 시크릿 프로바이더.
    AWS 환경에서 사용한다.
    """

    def __init__(self, region_name: Optional[str] = None):
        """
        AWSSecretsProvider 초기화.

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

        self.client = boto3.client("secretsmanager", region_name=region_name)
        self.region_name = region_name
        logger.info(f"AWS Secrets Provider initialized (region: {region_name or 'default'})")

    def get_secret(self, secret_name: str) -> str:
        """
        AWS Secrets Manager에서 시크릿 값을 가져온다.

        Args:
            secret_name: 시크릿 이름 또는 ARN

        Returns:
            str: 시크릿 값
        """
        try:
            response = self.client.get_secret_value(SecretId=secret_name)

            # SecretString 또는 SecretBinary 처리
            if "SecretString" in response:
                secret_value = response["SecretString"]
            else:
                # Binary secret인 경우 디코딩
                import base64
                secret_value = base64.b64decode(response["SecretBinary"]).decode("utf-8")

            logger.debug(f"Loaded secret from AWS Secrets Manager: {secret_name}")
            return secret_value
        except Exception as e:
            logger.error(f"Failed to load secret from AWS Secrets Manager '{secret_name}': {e}")
            raise RuntimeError(f"AWS Secrets Manager Error: {e}") from e

    def get_secret_json(self, secret_name: str) -> Dict[str, Any]:
        """
        JSON 형식의 시크릿을 파싱하여 반환한다.

        Args:
            secret_name: 시크릿 이름 또는 ARN

        Returns:
            Dict: 파싱된 JSON 딕셔너리
        """
        value = self.get_secret(secret_name)
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from AWS secret {secret_name}: {e}") from e
