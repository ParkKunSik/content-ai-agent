"""Secret Provider 기본 클래스"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class SecretProvider(ABC):
    """Secret Manager Provider 추상 클래스"""

    @abstractmethod
    def fetch_secrets(self, secret_id: str) -> Dict[str, Any]:
        """
        Secret Manager에서 설정을 가져온다.

        Args:
            secret_id: Secret 식별자

        Returns:
            설정 딕셔너리
        """
        pass
