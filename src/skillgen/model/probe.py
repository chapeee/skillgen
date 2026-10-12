"""What the runtime probe saw on a running page. Plain data; the probe fills it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from skillgen.model.page import Box, Limits, Strategy, ValueType


@dataclass(frozen=True)
class ProbedField:
    """One editable control seen on the rendered page.

    Attributes:
        key: Key derived from the control's name, id or label.
        label: The accessible name shown to users.
        selector: A selector checked to be unique on the page.
        strategy: How the probe filled the control.
        value_type: The kind of value, from the element type and role.
        is_required: True when the page marks the control as required.
        options: Visible option texts, for lists known on load.
        limits: Lengths, ranges and patterns from attributes.
        section: Label of the enclosing fieldset, region or tab.
        is_visible: True when the control was visible on load.
        is_proven: True when a synthetic value was filled and read back.
        selector_count: How many elements the selector matched (1 when unique).
        name: The control's `name` attribute.
        element_id: The control's `id` attribute.
        error_message: The client-side message shown when the empty form was submitted.
        is_repeated: True when the control belongs to a repeated row (`items[0][name]`).
        box: Where the control sat on load, in document coordinates; None when hidden.
    """

    key: str
    label: str
    selector: str
    strategy: Strategy
    value_type: ValueType
    is_required: bool = False
    options: tuple[str, ...] = ()
    limits: Limits = field(default_factory=Limits)
    section: str = ""
    is_visible: bool = True
    is_proven: bool = False
    selector_count: int = 1
    name: str = ""
    element_id: str = ""
    error_message: str = ""
    is_repeated: bool = False
    box: Box | None = None


@dataclass(frozen=True)
class ProbedCondition:
    """Setting a control to a value made other fields appear.

    Attributes:
        controller: Key of the control that was changed.
        value: The visible text of the value that was chosen.
        appeared: Keys of fields that became visible.
    """

    controller: str
    value: str
    appeared: tuple[str, ...]


@dataclass(frozen=True)
class ProbedDependency:
    """Changing a control reloaded another control's options.

    Attributes:
        controller: Key of the control that was changed.
        target: Key of the control whose options changed.
        is_async: True when a network request delivered the new options.
    """

    controller: str
    target: str
    is_async: bool = True


@dataclass(frozen=True)
class ProbedPage:
    """Everything the probe learned about one page.

    Attributes:
        url: The URL that was probed.
        title: The page heading or document title.
        fields: Controls in document order.
        conditions: Fields that appear on a value.
        dependencies: Option lists that depend on another control.
        submit_selector: Selector of the submit control.
        submit_label: Visible text of the submit control.
        body_shape: Keys and value types of the intercepted submit request; no values.
        has_empty_submit: True when the empty form was submitted, so a field without an
            error there is known to be optional.
        viewport_width: `innerWidth` while the boxes were measured; 0 when not measured.
        viewport_height: `innerHeight` while the boxes were measured; 0 when not measured.
        clickables: Everything the page offered to click, as the inventory reported it,
            with its own warnings (chrome, leaves, risky). Used to tell whether a part
            of the form was left unopened.
    """

    url: str
    title: str
    fields: tuple[ProbedField, ...]
    conditions: tuple[ProbedCondition, ...] = ()
    dependencies: tuple[ProbedDependency, ...] = ()
    submit_selector: str = ""
    submit_label: str = ""
    body_shape: dict[str, Any] = field(default_factory=dict)
    has_empty_submit: bool = False
    viewport_width: int = 0
    viewport_height: int = 0
    clickables: tuple[dict[str, Any], ...] = ()
