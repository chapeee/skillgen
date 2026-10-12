"""Consistency checks on a page model before a skill is written.

Every reference points at a real field, the dependency graph has no cycles, keys
and selectors are usable, and every probed selector was unique on the page.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from skillgen.model.page import (
    CHOICE_TYPES,
    PageModel,
    Strategy,
    list_dependencies,
)

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\[\]\.[a-z][a-z0-9_]*)?$")


def find_cycle(edges: list[tuple[str, str]]) -> list[str]:
    """Find one cycle in a directed graph.

    Args:
        edges: (source, target) pairs.

    Returns:
        The keys along a cycle, first key repeated at the end; empty when acyclic.
    """
    graph: dict[str, list[str]] = {}
    for source, target in edges:
        graph.setdefault(source, []).append(target)
    state: dict[str, int] = {}
    trail: list[str] = []

    def visit(node: str) -> list[str]:
        state[node] = 1
        trail.append(node)
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1:
                return [*trail[trail.index(nxt) :], nxt]
            if state.get(nxt) is None and (cycle := visit(nxt)):
                return cycle
        state[node] = 2
        trail.pop()
        return []

    for node in list(graph):
        if state.get(node) is None and (cycle := visit(node)):
            return cycle
    return []


def _check_references(page: PageModel) -> list[str]:
    keys = {spec.key for spec in page.fields}
    group_ids = {group.id for group in page.groups}
    section_ids = {section.id for section in page.sections}
    problems = [
        f"{link.target}: {link.kind} names unknown field {link.source!r}"
        for link in list_dependencies(page)
        if link.source not in keys
    ]
    for spec in page.fields:
        if spec.section and section_ids and spec.section not in section_ids:
            problems.append(f"{spec.key}: unknown section {spec.section!r}")
        if spec.group and spec.group not in group_ids:
            problems.append(f"{spec.key}: unknown group {spec.group!r}")
        if spec.group and not spec.key.startswith(f"{spec.group}[]."):
            problems.append(
                f"{spec.key}: keys in group {spec.group!r} must look like {spec.group}[].name"
            )
    problems += [
        f"rule {rule.text!r} names unknown field {rule.field!r}"
        for rule in page.rules
        if rule.field and rule.field not in keys and rule.field not in group_ids
    ]
    return problems


def _check_fields(page: PageModel) -> list[str]:
    problems = []
    seen: set[str] = set()
    for spec in page.fields:
        if spec.key in seen:
            problems.append(f"{spec.key}: key appears twice")
        seen.add(spec.key)
        if not KEY_PATTERN.match(spec.key):
            problems.append(f"{spec.key}: keys are snake_case (rows: group[].name)")
        if not spec.selector.strip():
            problems.append(f"{spec.key}: selector is empty")
        if spec.strategy is Strategy.NATIVE_SELECT and spec.value_type not in CHOICE_TYPES:
            problems.append(f"{spec.key}: a select must have an enum or multi-enum type")
    return problems


def check_page_model(
    page: PageModel, selector_counts: Mapping[str, int] | None = None
) -> list[str]:
    """Check a page model for internal consistency.

    Args:
        page: The page model.
        selector_counts: For a probed page, how many elements each field's selector
            matched; a selector that matched other than one element is reported.
            Choice fields match their whole group and are skipped.

    Returns:
        One message per problem; empty when the model is consistent.
    """
    problems = _check_fields(page) + _check_references(page)
    edges = [(link.source, link.target) for link in list_dependencies(page)]
    cycle = find_cycle(edges)
    if cycle:
        problems.append("dependency cycle: " + " → ".join(cycle))
    if page.submit is None:
        problems.append("page has no submit control")
    for spec in page.fields:
        count = (selector_counts or {}).get(spec.key)
        if (
            count is not None
            and spec.strategy is not Strategy.CHOICE
            and not spec.group
            and count != 1
        ):
            problems.append(f"{spec.key}: selector {spec.selector!r} matched {count} elements")
    return problems
