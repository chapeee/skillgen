"""Merge one field from Claude's analysis with what the probe saw on the page."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from skillgen.compile.assess import MISSING, Assessment, assess_fact
from skillgen.model.facts import Provenance, Source
from skillgen.model.page import (
    Condition,
    FieldSpec,
    Limits,
    Operator,
    OptionsSource,
    Strategy,
    ValueType,
)
from skillgen.model.probe import ProbedField, ProbedPage
from skillgen.model.route import Question
from skillgen.model.serialize import condition_from_dict, limits_from_dict, options_source_from_dict

IDENTITY = ("label", "selector", "strategy")
BEHAVIOUR = ("type", "required", "required_if", "visible_if", "options", "options_from", "limits")
DESCRIPTIVE = ("means", "format", "notes")


def normalize_text(text: str) -> str:
    """Lower-case text and collapse spaces, for comparisons.

    Args:
        text: Any text.

    Returns:
        The normalised text.
    """
    return " ".join(str(text).split()).lower()


def _same_options(code: Any, page: Any) -> bool:
    return {normalize_text(item) for item in code} == {normalize_text(item) for item in page}


# Types the page reports as plain text or a list that the code may describe more
# precisely; the code's type is kept when they agree.
_TYPE_REFINEMENTS = {
    "text": {"text", "email", "url", "phone", "number", "date"},
    "long-text": {"long-text", "rich-text", "text"},
    "enum": {"enum", "path"},
    "multi-enum": {"multi-enum"},
}


def _same_type(code: Any, page: Any) -> bool:
    return bool(code == page or code in _TYPE_REFINEMENTS.get(str(page), set()))


def _always_page(_code: Any, _page: Any) -> bool:
    """The page wins without a conflict (labels, selectors, proven strategies)."""
    return True


def _parse_options(text: str) -> tuple[str, ...]:
    separator = "·" if "·" in text else ","
    return tuple(item.strip() for item in text.split(separator) if item.strip())


def _parse_bool(text: str) -> bool:
    return text.strip().lower() in ("yes", "y", "true", "required")


@dataclass(frozen=True)
class FieldContext:
    """What every field merge needs to know.

    Attributes:
        skill: The skill name.
        answers: Developer answers by subject.
        probe: The probe's view of the page, if it ran.
    """

    skill: str
    answers: Mapping[str, str]
    probe: ProbedPage | None = None


def find_probed_field(raw: Mapping[str, Any], probe: ProbedPage | None) -> ProbedField | None:
    """Find the probed control that matches an analysed field.

    Matches by key, then selector, then name attribute, then label.

    Args:
        raw: The field from the analysis.
        probe: The probe result.

    Returns:
        The matching probed control, or None.
    """
    # The probe sees one control per row (`items[0][name]`); rows are matched by group.
    if probe is None or raw.get("group"):
        return None
    key, selector, label = (
        str(raw["key"]),
        str(raw.get("selector", "")),
        normalize_text(raw.get("label", "")),
    )
    tests: tuple[Callable[[ProbedField], bool], ...] = (
        lambda f: f.key == key,
        lambda f: bool(selector) and f.selector == selector,
        lambda f: bool(f.name) and (f.name == key or f"name={f.name}" in selector),
        lambda f: bool(label) and normalize_text(f.label) == label,
    )
    for test in tests:
        found = [probed for probed in probe.fields if not probed.is_repeated and test(probed)]
        if len(found) == 1:
            return found[0]
    return None


def _probe_condition(key: str, probe: ProbedPage | None) -> Any:
    if probe is None:
        return MISSING
    for condition in probe.conditions:
        if key in condition.appeared:
            return Condition(condition.controller, Operator.IN, (condition.value,))
    return MISSING


def _probe_options_source(key: str, probe: ProbedPage | None) -> Any:
    if probe is None:
        return MISSING
    for dependency in probe.dependencies:
        if dependency.target == key:
            return OptionsSource(depends_on=dependency.controller, is_async=dependency.is_async)
    return MISSING


def _merge_limits(code: Limits, page: Limits) -> Limits:
    """Code values first; the page fills the gaps."""
    return Limits(
        min_length=code.min_length if code.min_length is not None else page.min_length,
        max_length=code.max_length if code.max_length is not None else page.max_length,
        minimum=code.minimum if code.minimum is not None else page.minimum,
        maximum=code.maximum if code.maximum is not None else page.maximum,
        pattern=code.pattern or page.pattern,
        accept=code.accept or page.accept,
        max_size=code.max_size or page.max_size,
    )


def _page_values(probed: ProbedField | None, key: str, probe: ProbedPage | None) -> dict[str, Any]:
    """What the page says about each attribute; MISSING where it says nothing."""
    if probed is None:
        return dict.fromkeys((*IDENTITY, *BEHAVIOUR), MISSING) | {
            "visible_if": _probe_condition(key, probe),
            "options_from": _probe_options_source(key, probe),
        }
    return {
        "label": probed.label or MISSING,
        "selector": probed.selector,
        "strategy": probed.strategy.value if probed.is_proven else MISSING,
        "type": probed.value_type.value,
        # No `required` attribute proves nothing: apps often validate in script. Only
        # an empty submit that showed no error for the field says it is optional.
        "required": True
        if probed.is_required
        else (False if probe and probe.has_empty_submit else MISSING),
        "required_if": MISSING,
        "visible_if": _probe_condition(key, probe),
        # Tree pickers show only their top level until expanded; that is not the full list.
        "options": probed.options
        if probed.options and probed.value_type is not ValueType.PATH
        else MISSING,
        "options_from": _probe_options_source(key, probe),
        "limits": probed.limits if probed.limits != Limits() else MISSING,
    }


def _claimed_values(raw: Mapping[str, Any]) -> dict[str, Any]:
    """What the code (through Claude) says about each attribute."""
    limits = raw.get("limits")
    return {
        "label": raw.get("label") or MISSING,
        "selector": raw.get("selector") or MISSING,
        "strategy": raw.get("strategy") or MISSING,
        "type": raw.get("type") or MISSING,
        "required": bool(raw.get("required", False)),
        "required_if": condition_from_dict(raw.get("required_if")) or MISSING,
        "visible_if": condition_from_dict(raw.get("visible_if")) or MISSING,
        "options": tuple(raw.get("options") or ()) or MISSING,
        "options_from": options_source_from_dict(raw.get("options_from")) or MISSING,
        "limits": limits_from_dict(limits) if limits else MISSING,
        "means": raw.get("means") or MISSING,
        "format": raw.get("format") or MISSING,
        "notes": raw.get("notes") or MISSING,
    }


_COMPARE = {
    "label": _always_page,
    "selector": _always_page,
    "strategy": _always_page,
    "options": _same_options,
}
_PARSE = {"required": _parse_bool, "options": _parse_options}


def assess_field(raw: Mapping[str, Any], context: FieldContext) -> dict[str, Assessment]:
    """Assess every attribute of one analysed field.

    Args:
        raw: The field from the analysis.
        context: Skill, answers and probe.

    Returns:
        Assessments by attribute name.
    """
    key = str(raw["key"])
    inferred = set(raw.get("inferred", []))
    probed = find_probed_field(raw, context.probe)
    claimed, page = _claimed_values(raw), _page_values(probed, key, context.probe)
    if claimed["limits"] is not MISSING and page.get("limits", MISSING) is not MISSING:
        claimed["limits"] = page["limits"] = _merge_limits(claimed["limits"], page["limits"])
    results = {}
    for attribute, value in claimed.items():
        results[attribute] = assess_fact(
            context.skill,
            f"field:{key}:{attribute}",
            value,
            Source.CLAUDE_INFERRED if attribute in inferred else Source.EXTRACTED,
            page_value=page.get(attribute, MISSING),
            answers=context.answers,
            parse=_PARSE.get(attribute, str),
            same=_COMPARE.get(attribute, lambda a, b: a == b),
            label=f"{raw.get('label', key)} ({attribute.replace('_', ' ')})",
            should_keep_claimed=attribute == "type",
        )
    return results


def _value(results: Mapping[str, Assessment], attribute: str, default: Any) -> Any:
    found = results[attribute]
    return found.value if found.is_usable else default


def build_field(raw: Mapping[str, Any], results: Mapping[str, Assessment]) -> FieldSpec | None:
    """Build the field from its assessments, keeping only confident facts.

    Args:
        raw: The field from the analysis (for key, section and group).
        results: Assessments by attribute.

    Returns:
        The field, or None when its label, selector or strategy is not confident.
    """
    if not all(results[attribute].is_usable for attribute in IDENTITY):
        return None
    kept = [results[a] for a in (*IDENTITY, *BEHAVIOUR) if results[a].is_usable]
    sources = tuple(dict.fromkeys(source for found in kept for source in found.sources))
    return FieldSpec(
        key=str(raw["key"]),
        label=str(results["label"].value),
        value_type=ValueType(_value(results, "type", "text")),
        strategy=Strategy(results["strategy"].value),
        selector=str(results["selector"].value),
        provenance=Provenance(sources=sources, confidence=min(found.confidence for found in kept)),
        means=str(_value(results, "means", "")),
        format_hint=str(_value(results, "format", "")),
        options=tuple(_value(results, "options", ())),
        is_required=bool(_value(results, "required", False)),
        required_if=_value(results, "required_if", None),
        visible_if=_value(results, "visible_if", None),
        options_from=_value(results, "options_from", None),
        limits=_value(results, "limits", Limits()),
        section=str(raw.get("section", "")),
        group=str(raw.get("group", "")),
        notes=str(_value(results, "notes", "")),
        is_server_checked=bool(raw.get("server_checked", False)),
    )


def collect_questions(results: Mapping[str, Assessment]) -> list[Question]:
    """Questions raised by a field's facts; descriptive facts never ask.

    Args:
        results: Assessments by attribute.

    Returns:
        The questions, in attribute order.
    """
    return [
        found.question
        for attribute, found in results.items()
        if found.question is not None and attribute not in DESCRIPTIVE
    ]


def build_probed_only_field(probed: ProbedField) -> FieldSpec:
    """Build a field the probe saw but the analysis did not mention.

    Args:
        probed: The probed control.

    Returns:
        A field backed by the probe alone.
    """
    provenance = Provenance(sources=(Source.RUNTIME_PROBED,), confidence=0.9)
    spec = FieldSpec(
        key=probed.key,
        label=probed.label,
        value_type=probed.value_type,
        strategy=probed.strategy,
        selector=probed.selector,
        provenance=provenance,
        options=probed.options,
        is_required=probed.is_required,
        limits=probed.limits,
    )
    return replace(spec, section="") if not probed.section else spec
