"""Pydantic 모델에서 Schema Description을 추출하는 유틸리티"""

from typing import Any, Dict, Type

from pydantic import BaseModel


def extract_schema_description(
    model_class: Type[BaseModel],
    max_depth: int = 5
) -> str:
    """
    Pydantic 모델에서 필드별 description을 추출하여 프롬프트용 텍스트로 변환한다.

    Args:
        model_class: Pydantic BaseModel 서브클래스
        max_depth: 중첩 객체 탐색 최대 깊이

    Returns:
        str: 프롬프트에 포함할 schema description 텍스트
    """
    schema = model_class.model_json_schema()
    definitions = schema.get("$defs", {})

    lines = ["## Response Schema Field Descriptions", ""]
    _extract_properties(schema, definitions, lines, depth=0, max_depth=max_depth)

    return "\n".join(lines)


class SchemaDepthExceededError(Exception):
    """Schema 탐색 깊이가 max_depth를 초과했을 때 발생하는 예외"""
    pass


def _extract_properties(
    schema: Dict[str, Any],
    definitions: Dict[str, Any],
    lines: list,
    depth: int,
    max_depth: int,
    prefix: str = ""
) -> None:
    """재귀적으로 properties를 탐색하며 description을 추출한다."""
    if depth > max_depth:
        raise SchemaDepthExceededError(
            f"Schema depth exceeded max_depth={max_depth}. "
            f"Current prefix: '{prefix}'. Consider increasing max_depth."
        )

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    indent = "  " * depth

    for field_name, field_schema in properties.items():
        # $ref 해결
        if "$ref" in field_schema:
            ref_name = field_schema["$ref"].split("/")[-1]
            field_schema = definitions.get(ref_name, field_schema)

        description = field_schema.get("description", "")
        field_type = _get_field_type(field_schema, definitions)
        is_required = field_name in required

        # 필드 정보 출력
        field_path = f"{prefix}{field_name}" if prefix else field_name
        req_marker = "(required)" if is_required else "(optional)"
        lines.append(f"{indent}- **{field_path}** [{field_type}] {req_marker}: {description}")

        # 중첩 객체 탐색
        if field_schema.get("type") == "object" and "properties" in field_schema:
            _extract_properties(
                field_schema, definitions, lines,
                depth=depth + 1, max_depth=max_depth,
                prefix=f"{field_path}."
            )

        # 배열 내 객체 탐색
        if field_schema.get("type") == "array":
            items = field_schema.get("items", {})
            if "$ref" in items:
                ref_name = items["$ref"].split("/")[-1]
                items = definitions.get(ref_name, items)

            if items.get("type") == "object" and "properties" in items:
                lines.append(f"{indent}  Each item contains:")
                _extract_properties(
                    items, definitions, lines,
                    depth=depth + 2, max_depth=max_depth,
                    prefix=f"{field_path}[]."
                )


def _get_field_type(field_schema: Dict[str, Any], definitions: Dict[str, Any]) -> str:
    """필드의 타입을 문자열로 반환한다."""
    if "$ref" in field_schema:
        ref_name = field_schema["$ref"].split("/")[-1]
        return ref_name

    field_type = field_schema.get("type", "any")

    if field_type == "array":
        items = field_schema.get("items", {})
        if "$ref" in items:
            item_type = items["$ref"].split("/")[-1]
        else:
            item_type = items.get("type", "any")
        return f"array[{item_type}]"

    if "enum" in field_schema:
        return f"enum({', '.join(str(v) for v in field_schema['enum'])})"

    return field_type
