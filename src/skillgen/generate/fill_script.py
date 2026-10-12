"""Compile a page model into `scripts/fill.js`: a field map on top of the shared engine.

The map uses one-letter keys to keep the file small, because Claude reads it and
then sends it to the page in one evaluate call:

    k key · s selector · t strategy · r required · ri required-if · vi visible-if
    d options depend on · g repeat group · x compiled checks
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from skillgen import TOOL_NAME
from skillgen.model.page import (
    Check,
    Condition,
    FieldSpec,
    Limits,
    PageModel,
    Rule,
    ValueType,
)

ENGINE_VERSION = 1

# What binds the generated script's size is bytes, not lines: bytes are what a model
# pays for, and packing entries onto fewer lines does not make a file cheaper.
MAX_SCRIPT_BYTES = 48000
_NUMERIC_TYPES = frozenset({ValueType.NUMBER})

JsonDict = dict[str, Any]


def anchor_pattern(pattern: str) -> str:
    """Make a pattern match the whole value, as HTML `pattern` attributes do.

    Args:
        pattern: A regular expression, anchored or not.

    Returns:
        The pattern wrapped in `^(?:…)$` unless it is already anchored at both ends.
    """
    if pattern.startswith("^") and pattern.endswith("$") and not pattern.endswith("\\$"):
        return pattern
    return f"^(?:{pattern})$"


def _limit_value(value: str | None, value_type: ValueType) -> float | str | None:
    """Numbers compare as numbers in the page; dates compare as ISO strings."""
    if value is None:
        return None
    if value_type in _NUMERIC_TYPES:
        try:
            return float(value) if "." in value else int(value)
        except ValueError:
            return None
    return value


def compile_limits(limits: Limits, value_type: ValueType) -> JsonDict | None:
    """Turn a field's limits into one compiled check.

    Args:
        limits: The field's limits.
        value_type: The field's value type, which decides how min and max compare.

    Returns:
        The compiled check, or None when there is nothing to check.
    """
    compiled = {
        "p": anchor_pattern(limits.pattern) if limits.pattern else None,
        "ml": limits.min_length,
        "xl": limits.max_length,
        "mn": _limit_value(limits.minimum, value_type),
        "mx": _limit_value(limits.maximum, value_type),
    }
    kept = {key: value for key, value in compiled.items() if value is not None}
    return kept or None


def compile_check(check: Check, message: str = "") -> JsonDict | None:
    """Turn a rule's machine check into its compiled form.

    Args:
        check: The machine check.
        message: The rule text, returned by fill.js when the check fails.

    Returns:
        The compiled check, or None when the check is empty.
    """
    compiled: JsonDict = {
        "p": check.pattern or None,
        "ml": check.min_length,
        "xl": check.max_length,
        "mn": check.minimum,
        "mx": check.maximum,
        "nf": 1 if check.is_not_future else None,
    }
    kept = {key: value for key, value in compiled.items() if value is not None}
    if not kept:
        return None
    return kept | ({"m": message} if message else {})


def compile_condition(condition: Condition) -> JsonDict:
    """Turn a condition into its compiled form.

    Args:
        condition: The condition.

    Returns:
        `{"f": key, "o": operator, "v": [values]}`.
    """
    return {"f": condition.field, "o": condition.operator.value, "v": list(condition.values)}


def compile_field(spec: FieldSpec, rules: list[Rule]) -> JsonDict:
    """Build one field-map entry.

    Args:
        spec: The field.
        rules: Rules with a machine check that apply to this field.

    Returns:
        The compact map entry.
    """
    checks = [compile_limits(spec.limits, spec.value_type)]
    checks += [compile_check(rule.check, rule.text) for rule in rules if rule.check is not None]
    kept_checks = [check for check in checks if check]
    entry: JsonDict = {
        "k": spec.key,
        "s": spec.selector,
        "t": spec.strategy.value,
        "r": 1 if spec.is_required else None,
        "ri": compile_condition(spec.required_if) if spec.required_if else None,
        "vi": compile_condition(spec.visible_if) if spec.visible_if else None,
        "d": spec.options_from.depends_on if spec.options_from else None,
        "g": spec.group or None,
        "x": kept_checks or None,
    }
    return {key: value for key, value in entry.items() if value}


def find_host(app_url: str) -> str:
    """Return the hostname fill.js insists on, or an empty string when unknown.

    Args:
        app_url: The app's base URL.

    Returns:
        The hostname, such as `admin.example.com`.
    """
    return urlparse(app_url).hostname or "" if app_url else ""


def _to_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def build_fill_script(
    page: PageModel, engine_source: str, extra_rules: list[Rule] | None = None
) -> str:
    """Generate `scripts/fill.js` for a page.

    Args:
        page: The page model.
        engine_source: The shared engine's text, read at the edge and passed in so this
            module keeps no file access of its own.
        extra_rules: User and global rules whose machine checks are compiled too.

    Returns:
        The complete script.
    """
    rules = [rule for rule in (*page.rules, *(extra_rules or [])) if rule.field and rule.check]
    fields = [
        _to_json(compile_field(spec, [rule for rule in rules if rule.field == spec.key]))
        for spec in page.fields
    ]
    groups = [
        {
            "id": group.id,
            "row": group.row_selector,
            "add": group.add_selector,
            "min": group.min_rows,
        }
        for group in page.groups
    ]
    submit = page.submit
    submit_map = {
        "s": submit.selector if submit else "",
        "url": submit.success.url_matches if submit else "",
        "text": submit.success.text_appears if submit else "",
    }
    skill = {"name": page.skill, "host": find_host(page.app_url), "engine": ENGINE_VERSION}
    head = [
        f"/* {TOOL_NAME} fill.js for skill {page.skill}. Generated from the page model; "
        "regenerate instead of editing. */",
        "(function () {",
        "  'use strict';",
        f"  var SKILL = {_to_json(skill)};",
        f"  var SUBMIT = {_to_json(submit_map)};",
        f"  var GROUPS = {_to_json(groups)};",
        "  var FIELDS = [",
    ]
    engine = engine_source.rstrip("\n").split("\n")
    entries = [f"    {entry}," for entry in fields]
    return "\n".join([*head, *entries, "  ];", *engine]) + "\n"


def count_lines(script: str) -> int:
    """Count the lines of a script.

    Args:
        script: The script text.

    Returns:
        The number of lines.
    """
    return len(script.rstrip("\n").split("\n"))


# ES2020+ syntax the engine must not use; checked by tests and by validate/.
FORBIDDEN_SYNTAX = {
    "optional chaining": re.compile(r"\?\.(?![0-9])"),
    "nullish coalescing": re.compile(r"\?\?"),
    "logical assignment": re.compile(r"(\|\||&&|\?\?)="),
    "globalThis": re.compile(r"\bglobalThis\b"),
    "replaceAll": re.compile(r"\.replaceAll\("),
    "Array.at": re.compile(r"\.at\("),
    "Promise.allSettled": re.compile(r"\ballSettled\b"),
    "BigInt literal": re.compile(r"\b\d+n\b"),
    "private field": re.compile(r"\s#[A-Za-z_]"),
    "numeric separator": re.compile(r"\b\d+_\d+\b"),
}


def find_forbidden_syntax(script: str) -> list[str]:
    """List ES2020+ features used in a script, so fill.js stays ES2019.

    The scan is textual, so it can also flag such text inside string literals; the
    engine keeps none there.

    Args:
        script: JavaScript source.

    Returns:
        Names of the features found.
    """
    return [name for name, pattern in FORBIDDEN_SYNTAX.items() if pattern.search(script)]
