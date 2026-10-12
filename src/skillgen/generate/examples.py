"""Synthetic example values built from each field's constraints, never from real data."""

from __future__ import annotations

import re
from typing import Any

from skillgen.model.page import MANUAL_STRATEGIES, FieldSpec, PageModel, ValueType
from skillgen.validate.scan import scan_line

# A tiny regex generator: literals, classes, \d \w and fixed or ranged quantifiers.
_TOKEN = re.compile(
    r"\\d|\\w|\\.|\[(?:\\.|[^\]])+\]|[^\\()|?*+{}\[\]^$]|\{(\d+)(?:,(\d*))?\}|[?*+]"
)

_TEXT_BY_TYPE: dict[ValueType, Any] = {
    ValueType.EMAIL: "alex@example.com",
    ValueType.URL: "https://example.com",
    ValueType.PHONE: "555-0100",
    ValueType.DATE: "1990-01-15",
    ValueType.BOOLEAN: True,
    ValueType.RICH_TEXT: "Sample text for this field.",
    ValueType.LONG_TEXT: "Sample text for this field.",
}


def _first_of_class(token: str) -> str:
    """Pick a representative character from a regex class token."""
    if token in ("\\d",):
        return "1"
    if token in ("\\w", "."):
        return "a"
    if token.startswith("\\"):
        return token[1]
    if token.startswith("["):
        body = token[1:-1]
        if body.startswith("^"):
            return "x" if "x" not in body else "y"
        if len(body) >= 3 and body[1] == "-":
            return body[0]
        return body[0].lstrip("\\") or "a"
    return token


def example_from_pattern(pattern: str) -> str | None:
    r"""Build a string matching a simple regular expression.

    Supports literals, character classes, `\\d`, `\\w` and quantifiers. Patterns
    with groups or alternation are not supported.

    Args:
        pattern: The regular expression, with or without anchors.

    Returns:
        A matching string, or None when the pattern is too complex.
    """
    body = pattern.removeprefix("^").removesuffix("$")
    if any(mark in body for mark in "()|"):
        return None
    pieces: list[str] = []
    position = 0
    for match in _TOKEN.finditer(body):
        if match.start() != position:
            return None
        position = match.end()
        token = match.group(0)
        if token.startswith("{"):
            count = int(match.group(1))
            pieces[-1] = pieces[-1] * max(count, 1) if pieces else ""
        elif token == "+":
            continue
        elif token in "?*":
            if pieces:
                pieces.pop()
        else:
            pieces.append(_first_of_class(token))
    if position != len(body):
        return None
    candidate = "".join(pieces)
    return candidate if re.fullmatch(body, candidate) else None


def _sized_text(spec: FieldSpec) -> str:
    """Return sample text that respects min and max length."""
    text = f"Sample {spec.label.lower()}" if spec.label else "Sample text"
    minimum = spec.limits.min_length or 0
    maximum = spec.limits.max_length
    if len(text) < minimum:
        text = text + "x" * (minimum - len(text))
    if maximum is not None:
        text = text[:maximum]
    return text


def _number(spec: FieldSpec) -> int | float:
    """Return a number inside the field's range."""
    for bound in (spec.limits.minimum, spec.limits.maximum):
        if bound is not None:
            try:
                return float(bound) if "." in bound else int(bound)
            except ValueError:
                continue
    return 1


def build_example_value(spec: FieldSpec) -> Any:
    """Build a synthetic value that satisfies a field's constraints.

    Args:
        spec: The field.

    Returns:
        A JSON-compatible value, or None when no safe example exists (options
        loaded at run time, files, fields the user fills by hand).
    """
    if spec.strategy in MANUAL_STRATEGIES:
        return None
    if spec.value_type in (ValueType.ENUM, ValueType.PATH):
        return spec.options[0] if spec.options else None
    if spec.value_type is ValueType.MULTI_ENUM:
        return list(spec.options[:1]) or None
    if spec.value_type is ValueType.FILE:
        return None
    if spec.value_type is ValueType.NUMBER:
        return _number(spec)
    if spec.limits.pattern:
        candidate = example_from_pattern(spec.limits.pattern)
        if candidate is not None:
            # Some "patterns" are display masks (e.g. a phone input's "(000) 000-0000"
            # template) rather than true validation regexes, and get walked literally.
            # When that produces something that reads as real PII, prefer the type's
            # known-safe example instead of leaking a look-alike value.
            if spec.value_type in _TEXT_BY_TYPE and scan_line(candidate):
                return _TEXT_BY_TYPE[spec.value_type]
            return candidate
    if spec.value_type in _TEXT_BY_TYPE:
        return _TEXT_BY_TYPE[spec.value_type]
    return _sized_text(spec)


def build_example_values(page: PageModel, only_required: bool = False) -> dict[str, Any]:
    """Build an example `__fill` argument for a page.

    Group fields become a list with one row object under the group id.

    Args:
        page: The page model.
        only_required: Keep only fields that are always required.

    Returns:
        Values by key, in fill order; fields without a safe example are left out.
    """
    values: dict[str, Any] = {}
    rows: dict[str, dict[str, Any]] = {}
    for spec in page.fields:
        if only_required and not spec.is_required and not spec.group:
            continue
        value = build_example_value(spec)
        if value is None:
            continue
        if spec.group:
            rows.setdefault(spec.group, {})[spec.key.split("[].", 1)[-1]] = value
        else:
            values[spec.key] = value
    for group_id, row in rows.items():
        values[group_id] = [row]
    return values
