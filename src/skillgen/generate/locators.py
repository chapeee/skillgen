"""Render `references/locators.md`: every field as a role, a name, a selector and an action.

It serves browser tools that act on page elements by role, label or selector, such as
Playwright's `fill()`, `selectOption()`, `check()` and `click()`, but cannot run a page
script. It is data, never code: each tool maps it onto its own actions, and the skill
needs nothing installed.
"""

from __future__ import annotations

from collections.abc import Sequence

from skillgen.generate.inline_setter import PATH_SEPARATOR, field_selector, ordered_fields
from skillgen.generate.skill_md import (
    LOCATORS_REFERENCE,
    describe_condition,
    describe_submit_label,
)
from skillgen.model.page import FieldSpec, PageModel, Strategy, ValueType, View

LOCATORS_FILE = LOCATORS_REFERENCE

_ROLES = {
    Strategy.NATIVE_SELECT: "combobox",
    Strategy.ARIA_COMBOBOX: "combobox",
    Strategy.ARIA_TREE: "tree",
    Strategy.ARIA_LISTBOX: "listbox",
    Strategy.RICH_TEXT: "textbox",
}

_ACTIONS = {
    Strategy.ARIA_COMBOBOX: "`fill(value)`, wait for the list, then `click()` the option "
    "with that text",
    Strategy.ARIA_LISTBOX: "`click()` to open it, then `click()` each wanted option by text",
    Strategy.ARIA_TREE: f'`click()` each level of the path, split at "{PATH_SEPARATOR.strip()}"'
    ", in order",
    Strategy.RICH_TEXT: "`click()`, then type the text",
    Strategy.FILE: "`setInputFiles()` with the file the user gives",
    Strategy.STEPS: "ask the user to set it by hand",
}

# Inputs whose type has no ARIA role; they are found by their label instead.
_ROLELESS_TYPES = frozenset({ValueType.DATE, ValueType.FILE})


def find_field_role(spec: FieldSpec) -> str:
    """Name the ARIA role a field's control has, the way `getByRole` looks for it.

    Args:
        spec: The field.

    Returns:
        The role; empty when the control has none and is found by its label. Choice
        fields return the role of each option, which carries the option's own label.
    """
    if spec.strategy is Strategy.CHOICE:
        return "checkbox" if spec.value_type is ValueType.MULTI_ENUM else "radio"
    if spec.strategy is Strategy.NATIVE_SELECT and spec.value_type is ValueType.MULTI_ENUM:
        return "listbox"
    if spec.strategy is not Strategy.NATIVE_INPUT:
        return _ROLES.get(spec.strategy, "")
    if spec.value_type is ValueType.BOOLEAN:
        return "checkbox"
    if spec.value_type is ValueType.NUMBER:
        return "spinbutton"
    return "" if spec.value_type in _ROLELESS_TYPES else "textbox"


def describe_field_action(spec: FieldSpec) -> str:
    """Say which locator action sets a field, in Playwright's words.

    Args:
        spec: The field.

    Returns:
        Short text such as "`fill(value)`".
    """
    if spec.strategy in _ACTIONS:
        return _ACTIONS[spec.strategy]
    if spec.strategy is Strategy.CHOICE:
        if spec.value_type is ValueType.MULTI_ENUM:
            return "`check()` each wanted option, found by its label"
        return "`check()` the option whose label is the value"
    if spec.strategy is Strategy.NATIVE_SELECT:
        if spec.value_type is ValueType.MULTI_ENUM:
            return "`selectOption()` with every wanted label"
        return "`selectOption({ label: value })`"
    if spec.value_type is ValueType.BOOLEAN:
        return "`check()` for yes, `uncheck()` for no"
    return "`fill(value)`"


def describe_field_timing(spec: FieldSpec, page: PageModel) -> str:
    """Say when a field can be set: after a condition, a load, or inside a row.

    Args:
        spec: The field.
        page: The page, for labels of related fields.

    Returns:
        Short text; empty when the field can be set at any time.
    """
    notes = []
    if spec.visible_if is not None:
        notes.append("only when " + describe_condition(spec.visible_if, page))
    if spec.options_from is not None and spec.options_from.depends_on:
        controller = next(
            (item for item in page.fields if item.key == spec.options_from.depends_on), None
        )
        notes.append(f"after {controller.label if controller else spec.options_from.depends_on}")
    if spec.group:
        group = next((item for item in page.groups if item.id == spec.group), None)
        notes.append(f"in each {group.label if group and group.label else spec.group} row")
    return "; ".join(notes)


def describe_locator_clicks(steps: Sequence[str]) -> str:
    """Write clicks as locators: `getByText` for a label, `locator` for a selector.

    Args:
        steps: CSS selectors or `text:Label`.

    Returns:
        The clicks in order, joined with "then".
    """
    names = [
        f'`getByText("{step[5:].strip()}")`' if step.startswith("text:") else f'`locator("{step}")`'
        for step in steps
    ]
    return ", then ".join(names)


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def render_locator_table(fields: Sequence[FieldSpec], page: PageModel) -> list[str]:
    """Render one locator row per field.

    Args:
        fields: The fields, in fill order.
        page: The page model.

    Returns:
        Markdown lines.
    """
    lines = ["| Key | Role | Name | CSS | Do | When |", "|---|---|---|---|---|---|"]
    for spec in fields:
        selector = spec.selector if spec.group else field_selector(page, spec.key)
        name = "each option's label" if spec.strategy is Strategy.CHOICE else spec.label
        cells = [
            f"`{spec.key}`",
            find_field_role(spec),
            name,
            f"`{selector}`" if selector else "",
            describe_field_action(spec),
            describe_field_timing(spec, page),
        ]
        lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    return lines


def _view_heading(view: View, previous: View | None) -> list[str]:
    lines = [f"## {view.name}"]
    if previous is not None and previous.leave:
        lines.append(f"First close the part before: {describe_locator_clicks(previous.leave)}.")
    if view.enter:
        lines.append(f"Show it with {describe_locator_clicks(view.enter)}.")
    return [*lines, ""]


def split_by_view(page: PageModel) -> list[tuple[View | None, list[FieldSpec]]]:
    """Split the fields, in fill order, into runs that share the part they show in.

    Args:
        page: The page model.

    Returns:
        (view, fields) pairs; the view is None for fields shown with the form.
    """
    runs: list[tuple[View | None, list[FieldSpec]]] = []
    for spec in ordered_fields(page):
        view = page.view_of(spec.key)
        if runs and runs[-1][0] is view:
            runs[-1][1].append(spec)
        else:
            runs.append((view, [spec]))
    return runs


def render_field_blocks(page: PageModel) -> list[str]:
    """Render the locator tables, one per part of the form that shows after clicks.

    Args:
        page: The page model.

    Returns:
        Markdown lines.
    """
    lines: list[str] = []
    previous: View | None = None
    for view, fields in split_by_view(page):
        if view is not None:
            lines += _view_heading(view, previous)
        elif page.views:
            lines += ["## On the form", ""]
        lines += [*render_locator_table(fields, page), ""]
        previous = view
    return lines


def render_groups(page: PageModel) -> list[str]:
    """Render how to reach each repeating row.

    Args:
        page: The page model.

    Returns:
        Markdown lines; empty when the page has no repeating rows.
    """
    lines = []
    for group in page.groups:
        add = f" Add a row with `{group.add_selector}`." if group.add_selector else ""
        least = f" At least {group.min_rows} row(s) are needed." if group.min_rows else ""
        lines.append(
            f"- `{group.id}` ({group.label or group.id}): each row matches "
            f"`{group.row_selector}`; in row n, look for the field's CSS inside the n-th "
            f"match.{add}{least}"
        )
    return ["## Repeating rows", *lines, ""] if lines else []


def render_locators(page: PageModel) -> str:
    """Render `references/locators.md`.

    Args:
        page: The page model.

    Returns:
        The file content, ending with a newline.
    """
    opening = (
        [f"The form starts closed: click {describe_locator_clicks(page.open_steps)} first.", ""]
        if page.open_steps
        else []
    )
    submit = ""
    if page.submit is not None:
        submit = (
            f"Click {describe_submit_label(page)} (`{page.submit.selector}`) only when every "
            'field is done, as SKILL.md says under "Submit and verify".'
        )
    lines = [
        f"# {page.title} — locators",
        "",
        "For a browser tool that acts on elements by role, name or selector instead of running "
        "page scripts: `fill()`, `selectOption()`, `check()` and `click()` in Playwright's "
        "words, or the same actions under other names. Take values from the user; the options "
        "are in SKILL.md's field table.",
        "",
        "Find each field by its role and name (`getByRole(role, { name })`, or `getByLabel(name)` "
        "when the role is empty). If that finds nothing or several elements, use its CSS "
        "selector. Work in this order, and read each value back before submitting.",
        "",
        *opening,
        *render_field_blocks(page),
        *render_groups(page),
        *(["## Submit", submit] if submit else []),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"
