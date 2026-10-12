"""Convert a `PageModel` to and from the `page.json` document.

Defaults are omitted on write so `page.json` stays short and diffs stay readable.
Derived data (`dependencies`, section field lists) is written for readers but
recomputed, not trusted, on read.
"""

from __future__ import annotations

from typing import Any

from skillgen import TOOL_NAME
from skillgen.errors import ModelError
from skillgen.model.facts import Provenance, parse_sources
from skillgen.model.page import (
    PAGE_SCHEMA_VERSION,
    Box,
    Check,
    Condition,
    FieldSpec,
    Layout,
    Limits,
    Note,
    Operator,
    OptionsSource,
    PageModel,
    RepeatGroup,
    RouteParam,
    Rule,
    Section,
    Strategy,
    SubmitSpec,
    SuccessSignal,
    ValueType,
    View,
    list_dependencies,
)

# JSON documents are dictionaries of arbitrary JSON values.
JsonDict = dict[str, Any]

PAGE_SCHEMA_ID = f"{TOOL_NAME}.page/{PAGE_SCHEMA_VERSION}"


def _drop_empty(data: JsonDict) -> JsonDict:
    """Remove keys whose value is None, empty, or False, keeping zeros."""
    return {
        key: value
        for key, value in data.items()
        if value is not None and value is not False and value not in ("", [], {})
    }


def provenance_to_dict(provenance: Provenance) -> JsonDict:
    """Convert a provenance to its JSON form.

    Args:
        provenance: The provenance.

    Returns:
        `{"source": [...], "confidence": n}`.
    """
    return {
        "source": [source.value for source in provenance.sources],
        "confidence": provenance.confidence,
    }


def provenance_from_dict(data: JsonDict) -> Provenance:
    """Read a provenance from its JSON form.

    Args:
        data: An object with `source` (list of names) and `confidence`.

    Returns:
        The provenance.

    Raises:
        ModelError: If a source name is unknown.
    """
    try:
        sources = parse_sources(list(data.get("source", [])))
    except ValueError as error:
        raise ModelError(str(error)) from error
    return Provenance(sources=sources, confidence=float(data.get("confidence", 0.0)))


def box_to_list(box: Box) -> list[int]:
    """Convert a box to its compact JSON form.

    Args:
        box: The box.

    Returns:
        `[left, top, width, height]`.
    """
    return [box.left, box.top, box.width, box.height]


def box_from_list(data: Any) -> Box | None:
    """Read a box from its compact JSON form.

    Args:
        data: `[left, top, width, height]`, or None.

    Returns:
        The box, or None when there is none or it is malformed.
    """
    if not isinstance(data, (list, tuple)) or len(data) != 4:
        return None
    try:
        left, top, width, height = (round(float(value)) for value in data)
    except (TypeError, ValueError):
        return None
    if width <= 0 and height <= 0:
        return None
    return Box(left=left, top=top, width=width, height=height)


def viewport_from_list(data: Any) -> tuple[int, int]:
    """Read a viewport from its compact JSON form.

    Args:
        data: `[width, height]`, or anything else for an unmeasured viewport.

    Returns:
        `(width, height)`, with 0 for whatever is missing or malformed.
    """
    values = list(data) if isinstance(data, (list, tuple)) else []
    try:
        width = int(values[0]) if len(values) > 0 else 0
        height = int(values[1]) if len(values) > 1 else 0
    except (TypeError, ValueError):
        return 0, 0
    return width, height


def view_to_dict(view: View) -> JsonDict:
    """Serialize one view for `page.json`.

    Args:
        view: The view.

    Returns:
        `{name, enter, fields, leave}`, leave only when there is one.
    """
    data: JsonDict = {"name": view.name, "enter": list(view.enter), "fields": list(view.keys)}
    if view.leave:
        data["leave"] = list(view.leave)
    return data


def view_from_dict(data: JsonDict) -> View:
    """Read one view from `page.json` or an analysis.

    Args:
        data: The serialized view.

    Returns:
        The view.
    """
    return View(
        name=str(data.get("name", "")),
        enter=tuple(str(step) for step in data.get("enter", [])),
        keys=tuple(str(key) for key in data.get("fields", [])),
        leave=tuple(str(step) for step in data.get("leave", [])),
    )


def layout_to_dict(layout: Layout) -> JsonDict:
    """Convert a layout to its JSON form.

    Args:
        layout: The layout.

    Returns:
        The viewport, a box per field, and where the measurement came from.
    """
    return {
        "viewport": [layout.viewport_width, layout.viewport_height],
        "boxes": {key: box_to_list(box) for key, box in layout.boxes},
    } | provenance_to_dict(layout.provenance)


def layout_from_dict(data: JsonDict | None) -> Layout | None:
    """Read a layout from its JSON form.

    Args:
        data: The JSON object, or None.

    Returns:
        The layout, or None when there is none.

    Raises:
        ModelError: If a source name is unknown.
    """
    if not data:
        return None
    width, height = viewport_from_list(data.get("viewport"))
    boxes = []
    for key, raw in dict(data.get("boxes", {})).items():
        box = box_from_list(raw)
        if box is not None:
            boxes.append((str(key), box))
    return Layout(
        viewport_width=width,
        viewport_height=height,
        boxes=tuple(boxes),
        provenance=provenance_from_dict(data),
    )


def condition_to_dict(condition: Condition | None) -> JsonDict | None:
    """Convert a condition to JSON, or None when there is no condition.

    Args:
        condition: The condition.

    Returns:
        `{"field", "op", "values"}` or None.
    """
    if condition is None:
        return None
    return _drop_empty(
        {"field": condition.field, "op": condition.operator.value, "values": list(condition.values)}
    )


def condition_from_dict(data: JsonDict | None) -> Condition | None:
    """Read a condition from JSON.

    Args:
        data: The JSON object, or None.

    Returns:
        The condition, or None.
    """
    if not data:
        return None
    return Condition(
        field=str(data["field"]),
        operator=Operator(data.get("op", "in")),
        values=tuple(str(value) for value in data.get("values", [])),
    )


def _limits_to_dict(limits: Limits) -> JsonDict:
    return _drop_empty(
        {
            "min_length": limits.min_length,
            "max_length": limits.max_length,
            "minimum": limits.minimum,
            "maximum": limits.maximum,
            "pattern": limits.pattern,
            "accept": limits.accept,
            "max_size": limits.max_size,
        }
    )


def limits_from_dict(data: JsonDict) -> Limits:
    """Read field limits from JSON.

    Args:
        data: The `limits` object.

    Returns:
        The limits.
    """
    return Limits(
        min_length=data.get("min_length"),
        max_length=data.get("max_length"),
        minimum=None if data.get("minimum") is None else str(data["minimum"]),
        maximum=None if data.get("maximum") is None else str(data["maximum"]),
        pattern=str(data.get("pattern", "")),
        accept=str(data.get("accept", "")),
        max_size=str(data.get("max_size", "")),
    )


def _options_from_to_dict(source: OptionsSource | None) -> JsonDict | None:
    if source is None:
        return None
    return {
        "depends_on": source.depends_on,
        "load": "async" if source.is_async else "static",
        "pick_by": source.pick_by,
    }


def options_source_from_dict(data: JsonDict | None) -> OptionsSource | None:
    """Read where a field's options come from.

    Args:
        data: The `options_from` object, or None.

    Returns:
        The options source, or None.
    """
    if not data:
        return None
    return OptionsSource(
        depends_on=str(data.get("depends_on", "")),
        is_async=data.get("load") == "async",
        pick_by=str(data.get("pick_by", "text")),
    )


def field_to_dict(spec: FieldSpec) -> JsonDict:
    """Convert a field to its `page.json` form (without its key).

    Args:
        spec: The field.

    Returns:
        The JSON object for `fields[key]`.
    """
    data: JsonDict = {
        "label": spec.label,
        "means": spec.means,
        "type": spec.value_type.value,
        "format": spec.format_hint,
        "options": list(spec.options),
        "required": spec.is_required,
        "required_if": condition_to_dict(spec.required_if),
        "visible_if": condition_to_dict(spec.visible_if),
        "options_from": _options_from_to_dict(spec.options_from),
        "limits": _limits_to_dict(spec.limits),
        "strategy": spec.strategy.value,
        "selector": spec.selector,
        "section": spec.section,
        "group": spec.group,
        "notes": spec.notes,
        "server_checked": spec.is_server_checked,
    }
    return _drop_empty(data) | provenance_to_dict(spec.provenance)


def field_from_dict(key: str, data: JsonDict) -> FieldSpec:
    """Read one field from its `page.json` form.

    Args:
        key: The field key.
        data: The JSON object stored under `fields[key]`.

    Returns:
        The field.

    Raises:
        ModelError: If the type, strategy or a source is unknown.
    """
    try:
        value_type = ValueType(data.get("type", "text"))
        strategy = Strategy(data.get("strategy", "native-input"))
    except ValueError as error:
        raise ModelError(f"field {key!r}: {error}") from error
    return FieldSpec(
        key=key,
        label=str(data.get("label", key)),
        value_type=value_type,
        strategy=strategy,
        selector=str(data.get("selector", "")),
        provenance=provenance_from_dict(data),
        means=str(data.get("means", "")),
        format_hint=str(data.get("format", "")),
        options=tuple(str(option) for option in data.get("options", [])),
        is_required=bool(data.get("required", False)),
        required_if=condition_from_dict(data.get("required_if")),
        visible_if=condition_from_dict(data.get("visible_if")),
        options_from=options_source_from_dict(data.get("options_from")),
        limits=limits_from_dict(data.get("limits", {})),
        section=str(data.get("section", "")),
        group=str(data.get("group", "")),
        notes=str(data.get("notes", "")),
        is_server_checked=bool(data.get("server_checked", False)),
    )


def check_to_dict(check: Check | None) -> JsonDict | None:
    """Convert a machine check to JSON.

    Args:
        check: The check, or None.

    Returns:
        The JSON object, or None.
    """
    if check is None:
        return None
    return _drop_empty(
        {
            "pattern": check.pattern,
            "min": check.minimum,
            "max": check.maximum,
            "min_length": check.min_length,
            "max_length": check.max_length,
            "not_future": check.is_not_future,
        }
    )


def check_from_dict(data: JsonDict | None) -> Check | None:
    """Read a machine check from JSON.

    Args:
        data: The JSON object, or None.

    Returns:
        The check, or None.
    """
    if not data:
        return None
    return Check(
        pattern=str(data.get("pattern", "")),
        minimum=data.get("min"),
        maximum=data.get("max"),
        min_length=data.get("min_length"),
        max_length=data.get("max_length"),
        is_not_future=bool(data.get("not_future", False)),
    )


def _rule_to_dict(rule: Rule) -> JsonDict:
    data = _drop_empty({"text": rule.text, "field": rule.field, "check": check_to_dict(rule.check)})
    return data | provenance_to_dict(rule.provenance)


def _rule_from_dict(data: JsonDict) -> Rule:
    return Rule(
        text=str(data["text"]),
        provenance=provenance_from_dict(data),
        field=str(data.get("field", "")),
        check=check_from_dict(data.get("check")),
    )


def _submit_to_dict(submit: SubmitSpec | None) -> JsonDict | None:
    if submit is None:
        return None
    success = _drop_empty(
        {"url_matches": submit.success.url_matches, "text_appears": submit.success.text_appears}
    )
    return _drop_empty(
        {
            "selector": submit.selector,
            "label": submit.label,
            "success": success,
            "field_error": submit.field_error,
        }
    )


def _submit_from_dict(data: JsonDict | None) -> SubmitSpec | None:
    if not data:
        return None
    success = data.get("success", {})
    return SubmitSpec(
        selector=str(data["selector"]),
        label=str(data.get("label", "")),
        success=SuccessSignal(
            url_matches=str(success.get("url_matches", "")),
            text_appears=str(success.get("text_appears", "")),
        ),
        field_error=str(data.get("field_error", "[aria-invalid=true]")),
    )


def _sections_to_list(page: PageModel) -> list[JsonDict]:
    return [
        {
            "id": section.id,
            "label": section.label,
            "fields": [spec.key for spec in page.fields if spec.section == section.id],
        }
        for section in page.sections
    ]


def page_to_dict(page: PageModel) -> JsonDict:
    """Convert a page model to the `page.json` document.

    Args:
        page: The page model.

    Returns:
        The JSON document, ready for `json.dumps`.
    """
    data: JsonDict = {
        "schema": PAGE_SCHEMA_ID,
        "route": page.route,
        "skill": page.skill,
        "title": page.title,
        "app": _drop_empty({"name": page.app_name, "url": page.app_url}),
        "purpose": page.purpose,
        "verified": page.is_verified,
        "source_commit": page.source_commit,
        "version": page.version,
        "params": [_drop_empty({"name": p.name, "means": p.means}) for p in page.params],
        "sections": _sections_to_list(page),
        "groups": [
            _drop_empty(
                {
                    "id": group.id,
                    "label": group.label,
                    "row_selector": group.row_selector,
                    "add_selector": group.add_selector,
                    "min_rows": group.min_rows or None,
                }
            )
            for group in page.groups
        ],
        "fields": {spec.key: field_to_dict(spec) for spec in page.fields},
        "fill_order": [spec.key for spec in page.fields],
        "dependencies": [[d.source, d.target, d.kind] for d in list_dependencies(page)],
        "submit": _submit_to_dict(page.submit),
        "rules": [_rule_to_dict(rule) for rule in page.rules],
        "gotchas": [
            _drop_empty({"text": n.text}) | provenance_to_dict(n.provenance) for n in page.gotchas
        ],
        "layout": layout_to_dict(page.layout) if page.layout else None,
        "open": list(page.open_steps),
        "views": [view_to_dict(view) for view in page.views],
    }
    # `verified` is always written so a reader sees code-only skills at a glance.
    return _drop_empty(data) | {"verified": page.is_verified}


def _ordered_fields(data: JsonDict) -> tuple[FieldSpec, ...]:
    fields_data: JsonDict = data.get("fields", {})
    order: list[str] = list(data.get("fill_order", [])) or list(fields_data)
    unknown = [key for key in order if key not in fields_data]
    if unknown:
        raise ModelError(f"fill_order names unknown fields: {', '.join(unknown)}")
    # Fields missing from fill_order still belong to the page; they go last.
    order += [key for key in fields_data if key not in order]
    return tuple(field_from_dict(key, fields_data[key]) for key in order)


def page_from_dict(data: JsonDict) -> PageModel:
    """Read a page model from a `page.json` document.

    The document is expected to have passed schema validation already.

    Args:
        data: The parsed JSON document.

    Returns:
        The page model.

    Raises:
        ModelError: If the document is inconsistent.
    """
    app: JsonDict = data.get("app", {})
    return PageModel(
        route=str(data["route"]),
        skill=str(data["skill"]),
        title=str(data.get("title", "")),
        app_name=str(app.get("name", "")),
        app_url=str(app.get("url", "")),
        fields=_ordered_fields(data),
        purpose=str(data.get("purpose", "")),
        sections=tuple(
            Section(id=str(s["id"]), label=str(s.get("label", "")))
            for s in data.get("sections", [])
        ),
        groups=tuple(
            RepeatGroup(
                id=str(g["id"]),
                label=str(g.get("label", "")),
                row_selector=str(g.get("row_selector", "")),
                add_selector=str(g.get("add_selector", "")),
                min_rows=int(g.get("min_rows", 0)),
            )
            for g in data.get("groups", [])
        ),
        submit=_submit_from_dict(data.get("submit")),
        rules=tuple(_rule_from_dict(rule) for rule in data.get("rules", [])),
        gotchas=tuple(
            Note(text=str(n["text"]), provenance=provenance_from_dict(n))
            for n in data.get("gotchas", [])
        ),
        params=tuple(
            RouteParam(name=str(p["name"]), means=str(p.get("means", "")))
            for p in data.get("params", [])
        ),
        is_verified=bool(data.get("verified", False)),
        source_commit=str(data.get("source_commit", "")),
        version=int(data.get("version", 1)),
        layout=layout_from_dict(data.get("layout")),
        open_steps=tuple(str(step) for step in data.get("open", [])),
        views=tuple(view_from_dict(view) for view in data.get("views", [])),
    )
