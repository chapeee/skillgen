"""Turn the raw controls the page reported into probed fields. Pure."""

from __future__ import annotations

import re
from typing import Any

from skillgen.model.page import Limits, Strategy, ValueType
from skillgen.model.probe import ProbedField
from skillgen.model.serialize import box_from_list, limits_from_dict
from skillgen.routes.naming import slugify

_INPUT_TYPES = {
    "email": ValueType.EMAIL,
    "number": ValueType.NUMBER,
    "range": ValueType.NUMBER,
    "date": ValueType.DATE,
    "datetime-local": ValueType.DATE,
    "month": ValueType.DATE,
    "url": ValueType.URL,
    "tel": ValueType.PHONE,
    "textarea": ValueType.LONG_TEXT,
}
_INDEX = re.compile(r"\[\d+\]|\.\d+\.|_\d+_")


def make_key(raw: dict[str, Any]) -> str:
    """Derive a field key from a control's name, id or label.

    Args:
        raw: The control as the page reported it.

    Returns:
        A snake_case key.
    """
    for candidate in (raw.get("name", ""), raw.get("id", ""), raw.get("label", "")):
        cleaned = _INDEX.sub("_", str(candidate))
        key = slugify(cleaned).replace("-", "_")
        if key:
            return key if key[0].isalpha() else f"field_{key}"
    return "field"


def classify(raw: dict[str, Any]) -> tuple[Strategy, ValueType]:
    """Choose the fill strategy and value type for a control.

    Args:
        raw: The control as the page reported it (`kind` and `type`).

    Returns:
        (strategy, value type).
    """
    kind, kind_type = str(raw.get("kind", "input")), str(raw.get("type", "text"))
    is_multiple = kind_type == "multiple" or (kind == "choice" and kind_type == "checkbox")
    table: dict[str, tuple[Strategy, ValueType]] = {
        "choice": (Strategy.CHOICE, ValueType.MULTI_ENUM if is_multiple else ValueType.ENUM),
        "select": (Strategy.NATIVE_SELECT, ValueType.MULTI_ENUM if is_multiple else ValueType.ENUM),
        "combobox": (Strategy.ARIA_COMBOBOX, ValueType.ENUM),
        "tree": (Strategy.ARIA_TREE, ValueType.PATH),
        "listbox": (Strategy.ARIA_LISTBOX, ValueType.MULTI_ENUM if is_multiple else ValueType.ENUM),
        "rich-text": (Strategy.RICH_TEXT, ValueType.RICH_TEXT),
        "file": (Strategy.FILE, ValueType.FILE),
        "checkbox": (Strategy.NATIVE_INPUT, ValueType.BOOLEAN),
    }
    if kind in table:
        return table[kind]
    return Strategy.NATIVE_INPUT, _INPUT_TYPES.get(kind_type, ValueType.TEXT)


def build_probed_fields(controls: list[dict[str, Any]]) -> list[ProbedField]:
    """Build probed fields from the page's controls, with unique keys.

    Args:
        controls: Controls in document order.

    Returns:
        Probed fields in the same order.
    """
    fields: list[ProbedField] = []
    used: set[str] = set()
    for raw in controls:
        strategy, value_type = classify(raw)
        key = make_key(raw)
        while key in used:
            key += "_2"
        used.add(key)
        fields.append(
            ProbedField(
                key=key,
                label=str(raw.get("label", "")) or key,
                selector=str(raw.get("selector", "")),
                strategy=strategy,
                value_type=value_type,
                is_required=bool(raw.get("required", False)),
                options=tuple(
                    str(option) for option in raw.get("options", []) if str(option).strip()
                ),
                limits=limits_from_dict(raw.get("limits", {})) if raw.get("limits") else Limits(),
                section=str(raw.get("section", "")),
                is_visible=bool(raw.get("visible", True)),
                selector_count=int(raw.get("selector_count", 1)),
                name=str(raw.get("name", "")),
                element_id=str(raw.get("id", "")),
                is_repeated=bool(raw.get("repeated", False)),
                box=box_from_list(raw.get("box")),
            )
        )
    return fields


def describe_shape(body: str) -> dict[str, Any]:
    """Describe a request body by its keys and value types, never its values.

    Args:
        body: The raw request body.

    Returns:
        Key → type name (`string`, `number`, `boolean`, `list`, `object`, `null`).
    """
    import json  # noqa: PLC0415 - only needed here
    from urllib.parse import parse_qs  # noqa: PLC0415

    def type_name(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: type_name(item) for key, item in value.items()}
        if isinstance(value, list):
            return [type_name(value[0])] if value else []
        return {bool: "boolean", int: "number", float: "number", str: "string"}.get(
            type(value), "null"
        )

    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return dict.fromkeys(parse_qs(body or ""), "string")
    return type_name(parsed) if isinstance(parsed, dict) else {"(body)": type_name(parsed)}
