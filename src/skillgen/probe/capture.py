"""Save and read probe results (`pages/<skill>/probe/probe.json`). No Playwright needed."""

from __future__ import annotations

from typing import Any

from skillgen.model.page import Strategy, ValueType
from skillgen.model.probe import ProbedCondition, ProbedDependency, ProbedField, ProbedPage
from skillgen.model.serialize import (
    JsonDict,
    box_from_list,
    box_to_list,
    limits_from_dict,
    viewport_from_list,
)


def _limits_to_dict(probed: ProbedField) -> JsonDict:
    limits = probed.limits
    data = {
        "min_length": limits.min_length,
        "max_length": limits.max_length,
        "minimum": limits.minimum,
        "maximum": limits.maximum,
        "pattern": limits.pattern,
        "accept": limits.accept,
    }
    return {key: value for key, value in data.items() if value not in (None, "")}


def probed_field_to_dict(probed: ProbedField) -> JsonDict:
    """Convert a probed control to JSON.

    Args:
        probed: The control.

    Returns:
        The JSON object.
    """
    return {
        "key": probed.key,
        "label": probed.label,
        "selector": probed.selector,
        "strategy": probed.strategy.value,
        "type": probed.value_type.value,
        "required": probed.is_required,
        "options": list(probed.options),
        "limits": _limits_to_dict(probed),
        "section": probed.section,
        "visible": probed.is_visible,
        "proven": probed.is_proven,
        "selector_count": probed.selector_count,
        "name": probed.name,
        "id": probed.element_id,
        "error_message": probed.error_message,
        "repeated": probed.is_repeated,
        "box": box_to_list(probed.box) if probed.box else None,
    }


def probed_field_from_dict(data: dict[str, Any]) -> ProbedField:
    """Read a probed control from JSON.

    Args:
        data: The JSON object.

    Returns:
        The control.
    """
    return ProbedField(
        key=str(data["key"]),
        label=str(data.get("label", "")),
        selector=str(data["selector"]),
        strategy=Strategy(data.get("strategy", "native-input")),
        value_type=ValueType(data.get("type", "text")),
        is_required=bool(data.get("required", False)),
        options=tuple(str(option) for option in data.get("options", [])),
        limits=limits_from_dict(data.get("limits", {})),
        section=str(data.get("section", "")),
        is_visible=bool(data.get("visible", True)),
        is_proven=bool(data.get("proven", False)),
        selector_count=int(data.get("selector_count", 1)),
        name=str(data.get("name", "")),
        element_id=str(data.get("id", "")),
        error_message=str(data.get("error_message", "")),
        is_repeated=bool(data.get("repeated", False)),
        box=box_from_list(data.get("box")),
    )


def probed_page_to_dict(page: ProbedPage) -> JsonDict:
    """Convert a probe result to JSON.

    Args:
        page: The probe result.

    Returns:
        The JSON document.
    """
    # An inventory of clickables is written only when there is one, so a capture saved
    # before the inventory existed still reads back unchanged.
    extra = {"clickables": [dict(item) for item in page.clickables]} if page.clickables else {}
    return {
        "url": page.url,
        "title": page.title,
        "fields": [probed_field_to_dict(probed) for probed in page.fields],
        "conditions": [
            {"controller": c.controller, "value": c.value, "appeared": list(c.appeared)}
            for c in page.conditions
        ],
        "dependencies": [
            {"controller": d.controller, "target": d.target, "async": d.is_async}
            for d in page.dependencies
        ],
        "submit": {"selector": page.submit_selector, "label": page.submit_label},
        "body_shape": page.body_shape,
        "empty_submit": page.has_empty_submit,
        "viewport": [page.viewport_width, page.viewport_height],
        **extra,
    }


def probed_page_from_dict(data: dict[str, Any]) -> ProbedPage:
    """Read a probe result from JSON.

    Args:
        data: The JSON document.

    Returns:
        The probe result.
    """
    submit = data.get("submit", {})
    width, height = viewport_from_list(data.get("viewport"))
    return ProbedPage(
        url=str(data.get("url", "")),
        title=str(data.get("title", "")),
        fields=tuple(probed_field_from_dict(item) for item in data.get("fields", [])),
        conditions=tuple(
            ProbedCondition(str(c["controller"]), str(c["value"]), tuple(c.get("appeared", [])))
            for c in data.get("conditions", [])
        ),
        dependencies=tuple(
            ProbedDependency(str(d["controller"]), str(d["target"]), bool(d.get("async", True)))
            for d in data.get("dependencies", [])
        ),
        submit_selector=str(submit.get("selector", "")),
        submit_label=str(submit.get("label", "")),
        body_shape=dict(data.get("body_shape", {})),
        has_empty_submit=bool(data.get("empty_submit", False)),
        viewport_width=width,
        viewport_height=height,
        clickables=tuple(data.get("clickables", ())),
    )
