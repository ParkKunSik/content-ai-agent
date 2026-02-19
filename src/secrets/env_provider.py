"""Environment Variable Secret Provider"""

import json
import logging
import os
from typing import Any, Dict

from src.secrets.base import BaseSecretProvider

logger = logging.getLogger(__name__)


class EnvSecretProvider(BaseSecretProvider):
    """
    환경변수 기반 시크릿 프로바이더.
    로컬 개발 환경에서 사용한다.
    """

    def get_secret(self, secret_name: str) -> str:
        """
        환경변수에서 시크릿 값을 가져온다.

        Args:
            secret_name: 환경변수 이름

        Returns:
            str: 환경변수 값

        Raises:
            KeyError: 환경변수가 존재하지 않는 경우
        """
        value = os.environ.get(secret_name)
        if value is None:
            raise KeyError(f"Environment variable not found: {secret_name}")
        logger.debug(f"Loaded secret from environment: {secret_name}")
        return value

    def get_secret_json(self, secret_name: str) -> Dict[str, Any]:
        """
        JSON 형식의 환경변수를 파싱하여 반환한다.

        Args:
            secret_name: 환경변수 이름

        Returns:
            Dict: 파싱된 JSON 딕셔너리
        """
        value = self.get_secret(secret_name)
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from {secret_name}: {e}") from e
