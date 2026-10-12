"""Assemble every file of one skill folder in memory."""

from __future__ import annotations

import json
from dataclasses import replace

from skillgen.generate.evals import build_evals
from skillgen.generate.fill_script import build_fill_script
from skillgen.generate.layout_reference import LAYOUT_REFERENCE_FILE, render_layout_reference
from skillgen.generate.locators import LOCATORS_FILE, render_locators
from skillgen.generate.manual_steps import MANUAL_STEPS_FILE, render_manual_steps
from skillgen.generate.skill_md import (
    BODY_TOKEN_BUDGET,
    FILL_REFERENCE,
    MAX_INLINE_FIELDS,
    SkillText,
    render_fill_reference,
    render_references,
    render_skill_md,
    split_fields,
)
from skillgen.generate.user_rules import parse_user_rules
from skillgen.model.page import PageModel

SKILL_FILE = "SKILL.md"
SCRIPT_FILE = "scripts/fill.js"
REFERENCES_FILE = "references/fields.md"
EVALS_FILE = "evals/evals.json"
# Fields moved to references at a time while `SKILL.md` is over its budget.
FIELD_STEP = 4


def build_skill_files(
    page: PageModel,
    engine_source: str,
    user_block: str = "",
    global_rules: tuple[str, ...] = (),
    description: str = "",
) -> dict[str, str]:
    """Build the files of a skill folder.

    Args:
        page: The page model, already limited to confident facts.
        engine_source: The shared fill engine's text, read at the edge.
        user_block: The preserved user rules block from the previous `SKILL.md`.
        global_rules: Rules that apply to every page.
        description: A description chosen by the developer; built when empty.

    Returns:
        File contents by path relative to the skill folder.

    Raises:
        RuleError: If a user rule's check annotation is malformed.
    """
    text = fit_skill_text(
        page, SkillText(description=description, user_block=user_block, global_rules=global_rules)
    )
    references = render_references(page, text.inline_limit)
    global_block = "\n".join(f"- {rule}" for rule in global_rules)
    extra_rules = parse_user_rules(user_block) + parse_user_rules(global_block)
    files = {
        SKILL_FILE: render_skill_md(page, text),
        SCRIPT_FILE: build_fill_script(page, engine_source, extra_rules),
        EVALS_FILE: json.dumps(build_evals(page), indent=2, ensure_ascii=False) + "\n",
        # Every skill carries all four fill methods; the AI picks the one its browser
        # allows, and reads only that one's file.
        FILL_REFERENCE: render_fill_reference(page),
        LOCATORS_FILE: render_locators(page),
        MANUAL_STEPS_FILE: render_manual_steps(page),
    }
    if references:
        files[REFERENCES_FILE] = references
    layout = render_layout_reference(page)
    if layout:
        files[LAYOUT_REFERENCE_FILE] = layout
    return files


def fit_skill_text(page: PageModel, text: SkillText) -> SkillText:
    """Choose how many fields `SKILL.md` lists so its body stays inside the size budget.

    Long forms with steps, a layout check and many fields can outgrow the budget; the
    optional fields then move to `references/fields.md`, a few at a time, until it fits.
    Required fields never move.

    Args:
        page: The page model.
        text: The skill's text settings.

    Returns:
        The settings with the inline limit and `has_references` decided.
    """
    limit = MAX_INLINE_FIELDS
    while True:
        has_more = bool(split_fields(page, limit)[1])
        chosen = replace(text, inline_limit=limit, has_references=has_more)
        # The whole file is measured, so the frontmatter only adds a margin to the budget.
        tokens = (len(render_skill_md(page, chosen)) + 3) // 4
        if tokens <= BODY_TOKEN_BUDGET or limit <= FIELD_STEP:
            return chosen
        limit = min(limit, len(page.fields)) - FIELD_STEP


def with_skill_name(page: PageModel, name: str) -> PageModel:
    """Return the page model under another skill name.

    Args:
        page: The page model.
        name: The new name, already validated.

    Returns:
        A copy with `skill` set to `name`.
    """
    return replace(page, skill=name)
