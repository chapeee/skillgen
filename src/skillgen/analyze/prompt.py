"""The prompt Claude Code receives to analyse one route (spec section 5, step 3)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

PROMPT_VERSION = 3


@dataclass(frozen=True)
class AnalysisRequest:
    """Everything the analysis step needs for one route.

    Attributes:
        route: The route pattern.
        skill: The skill name.
        app_name: The app's display name.
        slice_files: Files that build the page, nearest first (relative paths).
        is_slice_truncated: True when the slice was cut at its cap.
        probe_summary: Facts the probe saw on the running page, if it ran.
        hint_facts: Facts hint packs already extracted, if any.
        connection_lines: Graphify's own account of the page's component and what it
            connects to; empty when Graphify has none.
    """

    route: str
    skill: str
    app_name: str
    slice_files: tuple[str, ...]
    is_slice_truncated: bool = False
    probe_summary: dict[str, Any] = field(default_factory=dict)
    hint_facts: tuple[str, ...] = ()
    connection_lines: tuple[str, ...] = ()


_RULES = """\
Rules for your answer:
- Read the files with your read-only tools. Read more files when the listed ones point
  to them (form components, validation schemas, API handlers, templates). Never edit.
- List every editable control a person can fill on this page, in the order they fill it.
  Skip hidden inputs, CSRF tokens, search boxes in the page chrome, and buttons: a button
  is never a field, but one that opens part of the form belongs in `open` or `views`.
- key: snake_case from the control's `name` attribute, else its id, else its label.
  Fields in repeatable rows use `group[].name`, and the group goes in `groups`.
- label: exactly as the page shows it. means: what the value represents, in the app's
  own words (labels, help text, validation messages). No business knowledge of your own.
- selector: a CSS selector that finds the rendered control: prefer [data-testid=…], then
  [name=…], then #id. For radio and checkbox groups, a selector matching every option.
  It must be valid CSS for the page as rendered: write the first row's real id
  (#contact_0_name), never a template such as {idx} or ${i}.
  For custom widgets, the element with the ARIA role (combobox input, tree, listbox).
- type: what the value is, never the HTML control. text, long-text (a textarea or any
  multi-line value), number, date, email, url, phone, boolean (one checkbox, or yes/no),
  enum (one option from a fixed set, including a radio group and a select), multi-enum
  (several of them), path (chosen level by level in a tree), file, rich-text. Never
  radio, checkbox, select or textarea: those are controls, and they go in strategy.
- strategy: native-input (inputs, textareas, single checkboxes), native-select, choice
  (radio or checkbox groups), aria-combobox (searchable dropdowns), aria-tree,
  aria-listbox (chips, custom lists), rich-text (contenteditable editors), file
  (uploads), steps (anything else).
- Passwords and other secrets: strategy steps, with notes saying the user types it
  themselves. A skill never asks for or fills a secret.
- options: the fixed list by visible text, only when the code states it. When options
  load at run time, leave options empty and fill options_from.
- required / required_if / visible_if: from attributes, validators and conditional
  rendering. Conditions name another field's key and its values by visible text.
- limits and rules: from the code's validation (client and server). Write each rule in
  plain words; add a machine check only when it is exact.
- inferred: name every attribute you deduced rather than read literally in the code.
  Facts you read literally are trusted more; be honest, it decides what reaches users.
- evidence: file and line for each field and rule. Evidence never reaches the skill.
- submit: the submit control, and how success shows: url_matches is plain text the URL
  contains afterwards (no regular expressions), or text_appears on the page. Set
  submit.inferred when the success signal is deduced rather than read in the code.
- open: when the form is not on screen as the page opens (its fields sit in a panel,
  tab, drawer or dialog that a click opens), list in steps what to click, in order,
  before the fields show. Each step is a CSS selector for the control (prefer
  [data-testid=…], then [aria-label=…] or [title=…], then #id), or text:Label for a
  button, link or tab whose text is exactly Label. Never name a click that saves,
  submits, deletes, signs out or leaves the page. Leave open out when the form shows on
  load. Set open.inferred when you deduced the steps rather than read them in the code.
- views: when some fields show only after a click once the form is open (wizard
  steps behind Next, tabs, accordion panels, a dialog opened by a button), list those
  parts in the order a person fills them. For each: name (what a person calls it, such
  as "Step 2: Employment" or "Address tab"), enter (what to click, from the view before,
  to show it; same step syntax as open, such as text:Next or text:Address), fields (the
  keys it shows) and, for a dialog, leave (what closes it after filling, such as
  text:Done). Fields in no view are the ones on screen once the form is open. Read it
  from the code: which state variable shows each part (v-show, v-if, a step counter, an
  active tab) and which control changes that state. Fields that appear because another
  field has a value are visible_if, not a view. Never name a click that submits, saves,
  deletes, signs out or leaves the page. Set inferred on a view you deduced.
- gotchas: short advice that prevents mistakes (a list that loads late, a button that
  stays disabled). questions: anything the code does not settle.
- Never copy real data from fixtures, seeds or tests: no names, emails, numbers or IDs.
- If the page has no editable controls, answer has_form: false with an empty fields list.
"""


def build_analysis_prompt(request: AnalysisRequest) -> str:
    """Write the analysis prompt for one route.

    Args:
        request: The route and what is known about it.

    Returns:
        The prompt text. The JSON schema is passed separately (`--json-schema`).
    """
    lines = [
        f"Analyse the page at route {request.route} of the app {request.app_name or '(unnamed)'}.",
        "Return one JSON object that matches the page-analysis schema. "
        f"Skill name: {request.skill}.",
        "",
        "Files that build this page, nearest first:",
        *[f"- {path}" for path in request.slice_files],
    ]
    if request.is_slice_truncated:
        lines.append("(The list was cut at its size limit; follow imports for anything missing.)")
    if request.connection_lines:
        lines += [
            "",
            "What the code graph knows about this page's own component: the symbols it "
            "holds, what it calls or imports, and where each is. Use it to find the "
            "files that matter, including a part of the form defined elsewhere:",
            *request.connection_lines,
        ]
    if request.probe_summary:
        lines += [
            "",
            "What the browser saw on this page. The keys, labels, selectors and options are "
            "what is really there, so use them as they are and let the code say what they "
            "mean. `clickable` lists what a person can click once the page's own menus, "
            "links away from it and anything costly are left out: use it to name the parts "
            "of the form that open on a click, and the controls that add a row.",
            json.dumps(request.probe_summary, indent=1, ensure_ascii=False),
        ]
    if request.hint_facts:
        lines += [
            "",
            "Facts already extracted from code by hint packs:",
            *[f"- {f}" for f in request.hint_facts],
        ]
    return "\n".join([*lines, "", _RULES])


def build_route_listing_prompt(
    app_name: str,
    hints: Sequence[tuple[str, Sequence[str], Sequence[str]]],
    known_routes: Sequence[str],
) -> str:
    """Write the prompt that asks Claude Code to list routes from a map of the code graph.

    Args:
        app_name: The app's display name.
        hints: (file, files it links to, why it was picked) for likely router files.
        known_routes: Routes already found, so Claude adds only what is missing.

    Returns:
        The prompt text.
    """
    lines = [
        f"List the user-facing page routes of the app {app_name or '(unnamed)'}.",
        "",
        "A code graph found these likely router or entry files. Each line shows what the file",
        "links to. Read them with read-only tools and follow the routing code; the route",
        "declarations may also be elsewhere (configuration, annotations, decorators, folders).",
    ]
    for file, links, reasons in hints:
        lines.append(f"- {file}  ({'; '.join(reasons)})")
        lines += [f"    → {link}" for link in links]
    if not hints:
        lines.append("- (no likely files; start from the repository's entry points)")
    if known_routes:
        lines += [
            "",
            "Already found (do not repeat them):",
            *[f"- {route}" for route in known_routes],
        ]
    lines += [
        "",
        "For every page a person can open in a browser, return route (with :name for",
        "parameters), entry_files (the file that renders the page first, then the file that",
        "declares the route), and title. Expand shorthand such as resource declarations into",
        "the individual pages they create. Skip API-only, asset and health-check routes.",
    ]
    return "\n".join(lines)
