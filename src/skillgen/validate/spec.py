"""Agent Skills spec checks on a generated skill folder (spec section 5, step 6).

Checks the frontmatter (parses, name rules, name equals folder, description quoted
and under 300 characters), the body size, and fill.js (line count, ES2019, engine
untouched). Works on file contents so it stays pure.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from skillgen.assets import read_fill_engine
from skillgen.generate.fill_script import MAX_SCRIPT_BYTES
from skillgen.generate.skill_md import BODY_TOKEN_BUDGET
from skillgen.routes.naming import MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH, is_valid_name

MAX_BODY_LINES = 500
MAX_BODY_TOKENS = BODY_TOKEN_BUDGET
MAX_COMPATIBILITY_LENGTH = 500
ALLOWED_KEYS = frozenset(
    {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
)
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def estimate_tokens(text: str) -> int:
    """Estimate tokens the way the size budget does: about four characters each.

    Args:
        text: Any text.

    Returns:
        The estimated token count.
    """
    return (len(text) + 3) // 4


def split_frontmatter(skill_md: str) -> tuple[str, str]:
    """Split `SKILL.md` into its raw frontmatter and its body.

    Args:
        skill_md: The file content.

    Returns:
        (frontmatter text without fences, body); frontmatter is empty when absent.
    """
    match = _FRONTMATTER.match(skill_md)
    if not match:
        return "", skill_md
    return match.group(1), skill_md[match.end() :]


def _check_name(data: Mapping[str, Any], folder_name: str) -> list[str]:
    name = data.get("name")
    if not isinstance(name, str) or not name:
        return ["frontmatter: `name` is missing"]
    problems = []
    if not is_valid_name(name):
        problems.append(
            f"name {name!r} must be 1–{MAX_NAME_LENGTH} lowercase letters, digits "
            "and single hyphens"
        )
    if folder_name and name != folder_name:
        problems.append(f"name {name!r} differs from its folder {folder_name!r}")
    return problems


def _check_description(data: Mapping[str, Any], raw: str) -> list[str]:
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        return ["frontmatter: `description` is missing"]
    problems = []
    if len(description) > MAX_DESCRIPTION_LENGTH:
        problems.append(
            f"description is {len(description)} characters; "
            f"keep it under {MAX_DESCRIPTION_LENGTH + 1}"
        )
    if not re.search(r"^description: \"", raw, re.MULTILINE):
        problems.append("description must be quoted in YAML")
    return problems


def _check_extras(data: Mapping[str, Any]) -> list[str]:
    problems = [f"frontmatter: unknown key {key!r}" for key in data if key not in ALLOWED_KEYS]
    compatibility = data.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str) or len(compatibility) > MAX_COMPATIBILITY_LENGTH
    ):
        problems.append("compatibility must be text of at most 500 characters")
    metadata = data.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            problems.append("metadata must be a mapping")
        else:
            problems += [
                f"metadata value for {key!r} must be a string"
                for key, value in metadata.items()
                if not isinstance(value, str)
            ]
    return problems


def check_skill_md(skill_md: str, folder_name: str = "") -> list[str]:
    """Check a `SKILL.md` against the Agent Skills spec and our size budget.

    Args:
        skill_md: The file content.
        folder_name: The folder the file lives in; empty to skip the match check.

    Returns:
        One message per problem; empty when the file passes.
    """
    raw, body = split_frontmatter(skill_md)
    if not raw:
        return ["SKILL.md must start with YAML frontmatter between --- lines"]
    # PyYAML costs about 80ms to import, which every command paid through this module
    # even when it checked no skill; it is loaded where the frontmatter is parsed.
    import yaml  # noqa: PLC0415 - import cost, see above

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        return [f"frontmatter does not parse: {error}"]
    if not isinstance(data, dict):
        return ["frontmatter must be a mapping"]
    problems = _check_name(data, folder_name) + _check_description(data, raw) + _check_extras(data)
    line_count = len(body.splitlines())
    if line_count >= MAX_BODY_LINES:
        problems.append(f"body has {line_count} lines; keep it under {MAX_BODY_LINES}")
    return problems


def find_size_notes(skill_md: str) -> list[str]:
    """Say when `SKILL.md` is over its token budget: a note, never a failure.

    The 500-line limit is the Agent Skills rule; the token budget is guidance. A long
    form's fill call carries every field's selector, so it can pass the budget even after
    the optional fields moved to `references/fields.md`, and the skill is still right.

    Args:
        skill_md: The file content.

    Returns:
        One note when the body is over the budget, else nothing.
    """
    _, body = split_frontmatter(skill_md)
    tokens = estimate_tokens(body)
    if tokens <= MAX_BODY_TOKENS:
        return []
    return [
        f"SKILL.md: body is about {tokens} tokens, over the {MAX_BODY_TOKENS} budget; "
        "optional fields were moved to references/fields.md where they could be"
    ]


def check_fill_script(script: str) -> list[str]:
    """Check `scripts/fill.js`: size and an untouched, ES2019 engine.

    Args:
        script: The script content.

    Returns:
        One message per problem; empty when the script passes.
    """
    problems = []
    size = len(script.encode("utf-8"))
    if size > MAX_SCRIPT_BYTES:
        problems.append(f"fill.js is {size} bytes; keep it under {MAX_SCRIPT_BYTES}")
    if not script.rstrip("\n").endswith(read_fill_engine().rstrip("\n")):
        problems.append("fill.js engine was edited by hand; regenerate the skill")
    return problems


def check_skill_files(files: Mapping[str, str], folder_name: str) -> list[str]:
    """Run every spec check on a skill folder's files.

    Args:
        files: File contents by path relative to the folder.
        folder_name: The folder's name.

    Returns:
        Problems, each prefixed with the file it concerns.
    """
    if "SKILL.md" not in files:
        return ["SKILL.md: missing"]
    problems = [f"SKILL.md: {p}" for p in check_skill_md(files["SKILL.md"], folder_name)]
    if "scripts/fill.js" in files:
        problems += [f"scripts/fill.js: {p}" for p in check_fill_script(files["scripts/fill.js"])]
    return problems
