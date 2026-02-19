"""
한글 문서화용 메타데이터 모듈

Annotated 타입 힌트에 추가하여 JSON Schema에 포함되지 않으면서
한글 설명을 유지할 수 있습니다.
"""
from typing import Type, get_args, get_type_hints

from pydantic import BaseModel


class KoDoc:
    """
    한글 문서화용 메타데이터 클래스

    Usage:
        name: Annotated[str, Field(description="English"), KoDoc("한글")]
    """

    def __init__(self, text: str):
        self.text = text

    def __repr__(self) -> str:
        return f"KoDoc({self.text!r})"


def get_field_ko_doc(model_class: Type[BaseModel], field_name: str) -> str | None:
    """
    모델 필드의 한글 설명을 추출합니다.

    Args:
        model_class: Pydantic 모델 클래스
        field_name: 필드 이름

    Returns:
        한글 설명 문자열, 없으면 None
    """
    try:
        hints = get_type_hints(model_class, include_extras=True)
        if field_name not in hints:
            return None

        args = get_args(hints[field_name])
        for arg in args[1:]:  # 첫 번째는 실제 타입
            if isinstance(arg, KoDoc):
                return arg.text
        return None
    except Exception:
        return None
