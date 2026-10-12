"""User rules: the block in `SKILL.md` that survives regeneration, and its checks.

Page rules live between the `<tool>:user:start` and `<tool>:user:end` markers. A rule
line may carry a machine check in backticks, which is compiled into fill.js:

    - Legal name must start with "A".  `check: legal_name ^A`
    - Age must be at least 18.  `check: age min 18`
    - Code has 4 to 8 characters.  `check: code length 4..8`
    - Start date cannot be in the future.  `check: start_date not-future`
"""

from __future__ import annotations

import re

from skillgen import TOOL_NAME
from skillgen.errors import RuleError
from skillgen.model.facts import Provenance, Source
from skillgen.model.page import Check, Rule

USER_START = f"<!-- {TOOL_NAME}:user:start -->"
USER_END = f"<!-- {TOOL_NAME}:user:end -->"
GENERATED_MARKER = f"<!-- {TOOL_NAME}:generated -->"

_CHECK = re.compile(r"`check:\s*([^`]+)`")
_USER_PROVENANCE = Provenance(sources=(Source.USER_DEFINED,), confidence=1.0)


def extract_user_block(skill_md: str) -> str:
    """Return the text between the user markers of an existing `SKILL.md`.

    Args:
        skill_md: The full text of a previously generated `SKILL.md`.

    Returns:
        The block without the markers, stripped; empty when there are no markers.
    """
    start = skill_md.find(USER_START)
    end = skill_md.find(USER_END)
    if start < 0 or end < start:
        return ""
    return skill_md[start + len(USER_START) : end].strip("\n")


def parse_check(text: str) -> tuple[str, Check]:
    """Parse the inside of a `` `check: …` `` annotation.

    Args:
        text: Such as `legal_name ^A`, `age min 18`, `code length 4..8`,
            or `start_date not-future`.

    Returns:
        The field key and its check.

    Raises:
        RuleError: If the annotation cannot be parsed.
    """
    parts = text.strip().split(None, 1)
    if len(parts) < 2:
        raise RuleError(f"check needs a field key and a condition: {text!r}")
    key, condition = parts[0], parts[1].strip()
    words = condition.split()
    try:
        if words[0] in ("min", "max") and len(words) == 2:
            number = float(words[1])
            return key, Check(minimum=number) if words[0] == "min" else Check(maximum=number)
        if words[0] == "length" and len(words) == 2 and ".." in words[1]:
            low, high = words[1].split("..", 1)
            return key, Check(min_length=int(low or 0), max_length=int(high) if high else None)
    except ValueError as error:
        raise RuleError(f"check has a bad number: {text!r}") from error
    if condition == "not-future":
        return key, Check(is_not_future=True)
    try:
        re.compile(condition)
    except re.error as error:
        raise RuleError(f"check pattern is not a valid regular expression: {text!r}") from error
    return key, Check(pattern=condition)


def parse_user_rules(block: str) -> list[Rule]:
    """Read the rules in a user block, compiling any `check:` annotations.

    Args:
        block: Text between the user markers, one rule per `- ` line.

    Returns:
        One rule per bullet line, with `USER_DEFINED` provenance.

    Raises:
        RuleError: If a check annotation is malformed.
    """
    rules = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("- ", "* ")):
            continue
        annotation = _CHECK.search(stripped)
        text = _CHECK.sub("", stripped[2:]).strip()
        if annotation:
            key, check = parse_check(annotation.group(1))
            rules.append(Rule(text=text, provenance=_USER_PROVENANCE, field=key, check=check))
        else:
            rules.append(Rule(text=text, provenance=_USER_PROVENANCE))
    return rules


def append_user_rule(block: str, text: str, check: str = "") -> str:
    """Add one rule line to a user block.

    Args:
        block: The current block (may be empty).
        text: The rule in plain words.
        check: An optional check annotation body, such as `legal_name ^A`.

    Returns:
        The new block.

    Raises:
        RuleError: If the text is empty or the check does not parse.
    """
    clean = " ".join(text.split())
    if not clean:
        raise RuleError("a rule needs some text")
    line = f"- {clean}"
    if check:
        parse_check(check)
        line += f"  `check: {check.strip()}`"
    return f"{block.rstrip()}\n{line}".strip("\n")
