"""Render `references/manual-steps.md`: the form as plain steps by what the page shows.

This is the last fill method: for a visual browser agent working from screenshots, or
for the person at the keyboard when no automated method works. It names fields by
their visible labels and parts of the form by their headings, never by selectors,
unless a click has nothing else to go by.
"""

from __future__ import annotations

from skillgen.generate.inline_setter import ordered_fields
from skillgen.generate.skill_md import (
    MANUAL_STEPS_REFERENCE,
    describe_accepts,
    describe_clicks,
    describe_condition,
    describe_open_steps,
    describe_page_url,
    describe_required,
    describe_submit_label,
    describe_success,
)
from skillgen.model.page import CHOICE_TYPES, FieldSpec, PageModel, Strategy, ValueType, View

MANUAL_STEPS_FILE = MANUAL_STEPS_REFERENCE

_STRATEGY_VERBS = {
    Strategy.ARIA_COMBOBOX: "type it, then pick it from the list that opens",
    Strategy.ARIA_TREE: "open the list and pick each level in turn",
    Strategy.RICH_TEXT: "click inside the editor and type it",
    Strategy.FILE: "upload the file the user gives",
    Strategy.STEPS: "set it as the page shows, or ask the user to",
}


def describe_manual_action(spec: FieldSpec) -> str:
    """Say what a person does to set a field, with what it accepts.

    Args:
        spec: The field.

    Returns:
        Text such as "type it (text, 3–80 chars)".
    """
    accepts = describe_accepts(spec)
    if spec.strategy in _STRATEGY_VERBS:
        verb = _STRATEGY_VERBS[spec.strategy]
    elif spec.value_type is ValueType.BOOLEAN:
        return "tick it for yes, leave it clear for no"
    elif spec.value_type is ValueType.MULTI_ENUM:
        verb = "tick each one wanted"
    elif spec.value_type in CHOICE_TYPES:
        verb = "choose one"
    else:
        verb = "type it"
    return f"{verb} ({accepts})" if accepts else verb


def describe_manual_field(spec: FieldSpec, page: PageModel) -> str:
    """Write one field as a step: label, action, and when it is needed or shown.

    Args:
        spec: The field.
        page: The page, for labels of related fields.

    Returns:
        One line of text.
    """
    parts = [f"{spec.label}: {describe_manual_action(spec)}."]
    required = describe_required(spec, page)
    if required == "yes":
        parts.append("Required.")
    elif required:
        parts.append(f"Required {required}.")
    if spec.visible_if is not None:
        parts.append(f"Shown only when {describe_condition(spec.visible_if, page)}.")
    if spec.options_from is not None and spec.options_from.depends_on:
        controller = next(
            (item for item in page.fields if item.key == spec.options_from.depends_on), None
        )
        parts.append(f"Its list fills in after {controller.label if controller else 'another'}.")
    return " ".join(parts)


def _place_of(spec: FieldSpec, page: PageModel) -> tuple[View | None, str]:
    """Where a field sits: its view, then its repeat group or else its section."""
    return page.view_of(spec.key), spec.group or spec.section


def _block_title(spec: FieldSpec, page: PageModel, view: View | None) -> str:
    if spec.group:
        group = next((item for item in page.groups if item.id == spec.group), None)
        name = group.label if group and group.label else spec.group
        return f"**{name}**, for each one the user gives (add another row if needed):"
    section = next((item for item in page.sections if item.id == spec.section), None)
    if section is not None and section.label:
        return f"**{section.label}**"
    return f"**{view.name}**" if view is not None else "**The form**"


def _view_steps(view: View, previous: View | None) -> list[str]:
    steps = []
    if previous is not None and previous.leave:
        steps.append(f"Click {describe_clicks(previous.leave)}.")
    if view.enter:
        steps.append(f"Click {describe_clicks(view.enter)} to show {view.name}.")
    return steps


def build_manual_steps(page: PageModel) -> list[list[str]]:
    """Build the numbered steps, each a heading line and its field bullets.

    Args:
        page: The page model.

    Returns:
        One list of lines per step, in the order a person does them.
    """
    steps: list[list[str]] = [[f"Open {describe_page_url(page)}."]]
    if page.open_steps:
        steps.append([f"Click {describe_open_steps(page)} to open the form."])
    current: tuple[View | None, str] | None = None
    for spec in ordered_fields(page):
        place = _place_of(spec, page)
        if place != current:
            if current is None or place[0] is not current[0]:
                previous = current[0] if current else None
                if place[0] is not None:
                    steps += [[line] for line in _view_steps(place[0], previous)]
            steps.append([_block_title(spec, page, place[0])])
            current = place
        steps[-1].append(f"    - {describe_manual_field(spec, page)}")
    success = describe_success(page)
    steps.append(
        [
            f"Check every value, then click {describe_submit_label(page)}, and only when the user "
            "has asked to submit." + (f" It worked if {success}." if success else "")
        ]
    )
    return steps


def render_manual_steps(page: PageModel) -> str:
    """Render `references/manual-steps.md`.

    Args:
        page: The page model.

    Returns:
        The file content, ending with a newline.
    """
    lines = [
        f"# {page.title} — by hand",
        "",
        "Plain steps by what the page shows, for when no automated method works: follow them "
        "with ordinary clicks and typing, or give them to the user. Take every value from the "
        "user and never invent one. If a login page, CAPTCHA or two-factor prompt appears, the "
        "user has to deal with it.",
        "",
    ]
    for number, step in enumerate(build_manual_steps(page), start=1):
        lines += [f"{number}. {step[0]}", *step[1:]]
    if page.gotchas:
        lines += ["", "## Watch out", *[f"- {note.text}" for note in page.gotchas]]
    return "\n".join(lines).rstrip("\n") + "\n"
