"""Secret Provider ABC"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseSecretProvider(ABC):
    """
    시크릿 관리를 위한 추상 베이스 클래스.
    환경변수, Google Secret Manager, AWS Secrets Manager 등을 지원한다.
    """

    @abstractmethod
    def get_secret(self, secret_name: str) -> str:
        """
        시크릿 값을 가져온다.

        Args:
            secret_name: 시크릿 이름

        Returns:
            str: 시크릿 값
        """
        pass

    @abstractmethod
    def get_secret_json(self, secret_name: str) -> Dict[str, Any]:
        """
        JSON 형식의 시크릿을 파싱하여 반환한다.

        Args:
            secret_name: 시크릿 이름

        Returns:
            Dict: 파싱된 JSON 딕셔너리
        """
        pass

    def get_secret_or_default(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        시크릿 값을 가져오거나 기본값을 반환한다.

        Args:
            secret_name: 시크릿 이름
            default: 기본값

        Returns:
            str or None: 시크릿 값 또는 기본값
        """
        try:
            return self.get_secret(secret_name)
        except Exception:
            return default
