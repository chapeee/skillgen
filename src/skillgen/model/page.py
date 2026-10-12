"""The page model: everything known about one route's form (`page.json`).

The model is plain frozen data. It holds what Claude needs to fill the page plus the
source and confidence of each fact; evidence lives elsewhere (`evidence.jsonl`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from skillgen.model.confidence import BASE_CONFIDENCE
from skillgen.model.facts import Provenance, Source

PAGE_SCHEMA_VERSION = 1


class Strategy(str, Enum):
    """How a field is filled (spec section 3, "Custom components")."""

    NATIVE_INPUT = "native-input"
    NATIVE_SELECT = "native-select"
    CHOICE = "choice"
    ARIA_COMBOBOX = "aria-combobox"
    ARIA_TREE = "aria-tree"
    ARIA_LISTBOX = "aria-listbox"
    RICH_TEXT = "rich-text"
    FILE = "file"
    STEPS = "steps"


class ValueType(str, Enum):
    """What kind of value a field takes."""

    TEXT = "text"
    LONG_TEXT = "long-text"
    NUMBER = "number"
    DATE = "date"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    ENUM = "enum"
    MULTI_ENUM = "multi-enum"
    BOOLEAN = "boolean"
    FILE = "file"
    PATH = "path"
    RICH_TEXT = "rich-text"


class Operator(str, Enum):
    """How a condition compares the controlling field's value."""

    IN = "in"
    NOT_IN = "not_in"
    CHECKED = "checked"
    FILLED = "filled"


# Strategies that fill.js cannot complete on its own: the user or the browser tool
# must act (uploads need the tool's file action; steps were not proven to work).
MANUAL_STRATEGIES = frozenset({Strategy.FILE, Strategy.STEPS})

# Value types that take one or more options from a list.
CHOICE_TYPES = frozenset({ValueType.ENUM, ValueType.MULTI_ENUM, ValueType.PATH})


@dataclass(frozen=True)
class Condition:
    """A condition on another field's value, used by `visible_if` and `required_if`.

    Attributes:
        field: Key of the controlling field.
        operator: How the controlling value is compared.
        values: Values for `in` and `not_in`; empty otherwise.
    """

    field: str
    operator: Operator
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionsSource:
    """Where a field's options come from when they are not a fixed list.

    Attributes:
        depends_on: Key of the field whose value changes the options, if any.
        is_async: True when options load from the server after a change.
        pick_by: Whether an option is chosen by its visible `text` or its `value`.
    """

    depends_on: str = ""
    is_async: bool = False
    pick_by: str = "text"


@dataclass(frozen=True)
class Limits:
    """Constraints on a field's value that the page or the code states.

    Attributes:
        min_length: Fewest characters allowed.
        max_length: Most characters allowed.
        minimum: Smallest number or earliest date (ISO string) allowed.
        maximum: Largest number or latest date (ISO string) allowed.
        pattern: Regular expression the whole value must match (JavaScript syntax).
        accept: File types accepted by an upload, as in the HTML `accept` attribute.
        max_size: Largest upload size, as written by the app (for example "2 MB").
    """

    min_length: int | None = None
    max_length: int | None = None
    minimum: str | None = None
    maximum: str | None = None
    pattern: str = ""
    accept: str = ""
    max_size: str = ""


@dataclass(frozen=True)
class FieldSpec:
    """One editable control on the page.

    Attributes:
        key: Stable key Claude uses in `__fill` (snake_case; `group[].name` in rows).
        label: The label shown on the page.
        value_type: What kind of value the field takes.
        strategy: How fill.js fills it.
        selector: CSS selector that finds the control (relative to its row in a group).
        provenance: Sources and confidence of the field as a whole.
        means: What the field represents, in the app's own words.
        format_hint: Accepted format in words, such as "YYYY-MM-DD".
        options: Allowed options, by visible text, when the list is fixed.
        is_required: True when the field is always required.
        required_if: Condition under which the field becomes required.
        visible_if: Condition under which the field appears.
        options_from: Where options come from when they change at run time.
        limits: Length, range, pattern and upload constraints.
        section: Id of the section the field belongs to.
        group: Id of the repeat group the field belongs to, if any.
        notes: Short extra advice for Claude.
        is_server_checked: True when only the server validates the field fully.
    """

    key: str
    label: str
    value_type: ValueType
    strategy: Strategy
    selector: str
    provenance: Provenance
    means: str = ""
    format_hint: str = ""
    options: tuple[str, ...] = ()
    is_required: bool = False
    required_if: Condition | None = None
    visible_if: Condition | None = None
    options_from: OptionsSource | None = None
    limits: Limits = field(default_factory=Limits)
    section: str = ""
    group: str = ""
    notes: str = ""
    is_server_checked: bool = False


@dataclass(frozen=True)
class Section:
    """A visible group of fields, such as a fieldset, card or tab.

    Attributes:
        id: Stable id.
        label: Heading shown on the page.
    """

    id: str
    label: str


@dataclass(frozen=True)
class RepeatGroup:
    """Rows of fields the user can add, such as several directors.

    Attributes:
        id: Key used in `__fill` for the list of row values.
        label: Name of one row, as the page shows it.
        row_selector: CSS selector matching each row.
        add_selector: CSS selector of the control that adds a row.
        min_rows: Fewest rows the form accepts.
    """

    id: str
    label: str
    row_selector: str
    add_selector: str
    min_rows: int = 0


@dataclass(frozen=True)
class Check:
    """A machine check compiled into fill.js. Unset parts are not checked.

    Attributes:
        pattern: Regular expression the value must match (JavaScript syntax).
        minimum: Smallest allowed number.
        maximum: Largest allowed number.
        min_length: Fewest characters.
        max_length: Most characters.
        is_not_future: For dates: must not be after today.
    """

    pattern: str = ""
    minimum: float | None = None
    maximum: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    is_not_future: bool = False


@dataclass(frozen=True)
class Rule:
    """A rule the value must follow, in words and optionally as a check.

    Attributes:
        text: The rule in plain words.
        provenance: Sources and confidence.
        field: Key of the field the rule applies to, if it applies to one.
        check: The machine check, if the rule can be checked in the page.
    """

    text: str
    provenance: Provenance
    field: str = ""
    check: Check | None = None


@dataclass(frozen=True)
class Note:
    """A gotcha or other advice, with its provenance.

    Attributes:
        text: The advice in plain words.
        provenance: Sources and confidence.
    """

    text: str
    provenance: Provenance


@dataclass(frozen=True)
class SuccessSignal:
    """How to tell the submit worked. Empty parts are not checked.

    Attributes:
        url_matches: Substring or `/regex/` the URL contains after success.
        text_appears: Text that appears on the page after success.
    """

    url_matches: str = ""
    text_appears: str = ""


@dataclass(frozen=True)
class SubmitSpec:
    """How to submit the form and read the result.

    Attributes:
        selector: CSS selector of the submit control.
        label: Visible text of the submit control.
        success: How to tell the submit worked.
        field_error: CSS selector of controls marked invalid after a failed submit.
    """

    selector: str
    label: str = ""
    success: SuccessSignal = field(default_factory=SuccessSignal)
    field_error: str = "[aria-invalid=true]"


@dataclass(frozen=True)
class RouteParam:
    """A parameter in the route, such as `id` in `/projects/:id/edit`.

    Attributes:
        name: Parameter name.
        means: What it identifies, in the app's words.
    """

    name: str
    means: str = ""


@dataclass(frozen=True)
class Box:
    """Where a control sat on the page when it was measured, in CSS pixels.

    Positions are document coordinates (the viewport position plus the scroll), so a
    box does not depend on how far the page was scrolled when it was read.

    Attributes:
        left: Distance from the document's left edge.
        top: Distance from the document's top edge.
        width: Rendered width.
        height: Rendered height.
    """

    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class Layout:
    """The page as the probe saw it: the viewport and where each visible field sat.

    A layout lets a skill check that the page in front of it is the page it was built
    from before it trusts what it knows. It is never used to aim a click: anything
    clicked is measured again on the screen at hand.

    Attributes:
        viewport_width: `innerWidth` when the page was measured.
        viewport_height: `innerHeight` when the page was measured.
        boxes: Field key and box, for every field that was visible on load.
        provenance: Where the measurement came from.
    """

    viewport_width: int
    viewport_height: int
    boxes: tuple[tuple[str, Box], ...]
    provenance: Provenance = field(
        default_factory=lambda: Provenance(
            sources=(Source.RUNTIME_PROBED,),
            confidence=BASE_CONFIDENCE[Source.RUNTIME_PROBED],
        )
    )

    def box_of(self, key: str) -> Box | None:
        """Return the box measured for a field.

        Args:
            key: The field key.

        Returns:
            The box, or None when the field was not visible on load.
        """
        return next((box for name, box in self.boxes if name == key), None)


@dataclass(frozen=True)
class View:
    """A part of the page that shows only after clicks: a step, tab, dialog or panel.

    Views are kept in the order a person goes through them, and each one says how to
    get to it from the view before, so walking them in order reaches every field.

    Attributes:
        name: What a person calls it, such as `Step 2: Employment`.
        enter: What to click, in order, to show it from the view before: a CSS selector
            or `text:Label`.
        keys: The fields it shows.
        leave: What to click after filling it, before the next view (closing a dialog).
    """

    name: str
    enter: tuple[str, ...]
    keys: tuple[str, ...]
    leave: tuple[str, ...] = ()


@dataclass(frozen=True)
class PageModel:
    """Everything known about one route's form.

    Attributes:
        route: The route pattern, such as `/developer/kyc`.
        skill: The skill name (folder name).
        title: The page title.
        app_name: The app's display name.
        app_url: Base URL the skill is meant for; empty when unknown.
        fields: Every field, in fill order.
        purpose: One or two sentences on what saving the page does.
        sections: Sections in page order.
        groups: Repeat groups.
        submit: How to submit, if the page has a submit control.
        rules: Rules beyond the per-field limits.
        gotchas: Advice that prevents common mistakes.
        params: Route parameters Claude must ask for or look up.
        is_verified: True when every required field was proven by the probe.
        source_commit: Commit the model was generated from.
        version: Bumped on every regeneration that changes the model.
        layout: Where fields sat when the probe measured the page; None without a probe.
        open_steps: What to click, in order, before the form is on screen.
        views: Parts of the form shown only after clicks, in the order they are filled;
            fields in none of them are on screen once the form is open.
    """

    route: str
    skill: str
    title: str
    app_name: str
    app_url: str
    fields: tuple[FieldSpec, ...]
    purpose: str = ""
    sections: tuple[Section, ...] = ()
    groups: tuple[RepeatGroup, ...] = ()
    submit: SubmitSpec | None = None
    rules: tuple[Rule, ...] = ()
    gotchas: tuple[Note, ...] = ()
    params: tuple[RouteParam, ...] = ()
    is_verified: bool = False
    source_commit: str = ""
    version: int = 1
    layout: Layout | None = None
    open_steps: tuple[str, ...] = ()
    views: tuple[View, ...] = ()

    def view_of(self, key: str) -> View | None:
        """Return the view that shows a field, or None when it shows with the form.

        Args:
            key: The field key.

        Returns:
            The view, or None.
        """
        return next((view for view in self.views if key in view.keys), None)


@dataclass(frozen=True)
class Dependency:
    """A link from one field to another, derived from the fields.

    Attributes:
        source: Key of the controlling field.
        target: Key of the field it affects.
        kind: `options_from`, `visible_if` or `required_if`.
    """

    source: str
    target: str
    kind: str


def find_field(page: PageModel, key: str) -> FieldSpec | None:
    """Return the field with the given key, or None.

    Args:
        page: The page model.
        key: The field key.

    Returns:
        The matching field, or None when no field has that key.
    """
    for candidate in page.fields:
        if candidate.key == key:
            return candidate
    return None


def list_dependencies(page: PageModel) -> list[Dependency]:
    """List every dependency between fields, in fill order.

    Args:
        page: The page model.

    Returns:
        One entry per `options_from`, `visible_if` and `required_if` link.
    """
    links: list[Dependency] = []
    for spec in page.fields:
        if spec.options_from is not None and spec.options_from.depends_on:
            links.append(Dependency(spec.options_from.depends_on, spec.key, "options_from"))
        if spec.visible_if is not None:
            links.append(Dependency(spec.visible_if.field, spec.key, "visible_if"))
        if spec.required_if is not None:
            links.append(Dependency(spec.required_if.field, spec.key, "required_if"))
    return links


def make_provenance(sources: tuple[Source, ...], confidence: float) -> Provenance:
    """Build a `Provenance`, rounding the confidence to three decimals.

    Args:
        sources: The sources of the fact.
        confidence: The combined confidence.

    Returns:
        The provenance record.
    """
    return Provenance(sources=sources, confidence=round(confidence, 3))
