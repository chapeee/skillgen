"""Merge Claude's analysis, probe facts and developer answers into a page model.

Deterministic and pure (spec section 5, step 4). Every fact gets a source and a
confidence; facts below 0.7 stay out of the skill, and conflicts become questions.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from skillgen.compile.assess import MISSING, assess_fact, make_question_id
from skillgen.compile.fields import (
    FieldContext,
    assess_field,
    build_field,
    build_probed_only_field,
    collect_questions,
    find_probed_field,
)
from skillgen.compile.layout import build_layout
from skillgen.model.facts import Evidence, Provenance, Source
from skillgen.model.page import (
    FieldSpec,
    Note,
    PageModel,
    RepeatGroup,
    RouteParam,
    Rule,
    Section,
    SubmitSpec,
    SuccessSignal,
    View,
)
from skillgen.model.probe import ProbedPage
from skillgen.model.route import Question
from skillgen.model.serialize import check_from_dict, view_from_dict
from skillgen.routes.naming import find_route_params

AnalysisDocument = Mapping[str, Any]


@dataclass(frozen=True)
class MergeInput:
    """Everything known about one route.

    Attributes:
        route: The route pattern.
        skill: The skill name.
        analysis: Claude's validated page analysis.
        app_name: The app's display name.
        app_url: The app's base URL; empty when unknown.
        probe: The probe's view of the page, if it ran.
        answers: Developer answers by question subject.
        source_commit: The commit the code was read at.
        version: The page model version to write.
    """

    route: str
    skill: str
    analysis: AnalysisDocument
    app_name: str = ""
    app_url: str = ""
    probe: ProbedPage | None = None
    answers: Mapping[str, str] = field(default_factory=dict)
    source_commit: str = ""
    version: int = 1


@dataclass(frozen=True)
class MergeResult:
    """The merged page and what still needs the developer.

    Attributes:
        page: The page model with confident facts only.
        questions: Open questions for the developer.
        evidence: Where each fact was seen; stays in `.skillgen/`.
    """

    page: PageModel
    questions: tuple[Question, ...]
    evidence: tuple[Evidence, ...]


def _source_of(item: Mapping[str, Any]) -> Source:
    return Source.CLAUDE_INFERRED if item.get("inferred") else Source.EXTRACTED


def merge_fields(data: MergeInput) -> tuple[list[FieldSpec], list[Question]]:
    """Merge every analysed field, then add fields only the probe saw.

    Args:
        data: The merge input.

    Returns:
        (fields in fill order, questions).
    """
    context = FieldContext(data.skill, data.answers, data.probe)
    fields: list[FieldSpec] = []
    questions: list[Question] = []
    matched: set[str] = set()
    for raw in data.analysis.get("fields", []):
        probed = find_probed_field(raw, data.probe)
        if probed is not None:
            matched.add(probed.key)
        elif data.probe is not None and not raw.get("visible_if") and not raw.get("group"):
            presence = _assess_unseen(raw, data)
            questions += [presence.question] if presence.question else []
            if not presence.is_usable:
                continue
        results = assess_field(raw, context)
        questions += collect_questions(results)
        spec = build_field(raw, results)
        if spec is not None:
            fields.append(spec)
    if data.probe is not None:
        known = {spec.key for spec in fields}
        fields += [
            build_probed_only_field(probed)
            for probed in data.probe.fields
            if probed.key not in matched
            and probed.key not in known
            and probed.is_visible
            and not probed.is_repeated
        ]
    return fields, questions


def _assess_unseen(raw: Mapping[str, Any], data: MergeInput) -> Any:
    """A field in the code that the probe did not see on the page is a conflict."""
    key = str(raw["key"])
    return assess_fact(
        data.skill,
        f"field:{key}:presence",
        True,
        Source.EXTRACTED,
        page_value=False,
        answers=data.answers,
        label=f"whether {raw.get('label', key)} is on the page",
    )


def merge_rules(data: MergeInput) -> tuple[list[Rule], list[Question]]:
    """Keep confident rules; ask about the others.

    Args:
        data: The merge input.

    Returns:
        (rules, questions).
    """
    rules, questions = [], []
    for index, raw in enumerate(data.analysis.get("rules", []), start=1):
        found = assess_fact(
            data.skill,
            f"rule:{index}",
            raw["text"],
            _source_of(raw),
            answers=data.answers,
            label="this rule",
        )
        if found.question:
            questions.append(found.question)
        if found.is_usable:
            provenance = Provenance(found.sources, found.confidence)
            rules.append(
                Rule(
                    str(found.value),
                    provenance,
                    str(raw.get("field", "")),
                    check_from_dict(raw.get("check")),
                )
            )
    return rules, questions


def merge_gotchas(data: MergeInput) -> tuple[list[Note], list[Question]]:
    """Keep confident gotchas, and ask about the ones Claude deduced.

    A deduced gotcha stays out of the skill until the developer confirms it, like any
    other fact; it is asked about rather than dropped, because advice such as "saving
    clears every field you leave empty" is exactly what a reader must not miss.

    Args:
        data: The merge input.

    Returns:
        (the notes, questions about deduced ones).
    """
    notes: list[Note] = []
    questions: list[Question] = []
    for index, raw in enumerate(data.analysis.get("gotchas", []), start=1):
        found = assess_fact(
            data.skill,
            f"gotcha:{index}",
            raw["text"],
            _source_of(raw),
            answers=data.answers,
            label="advice for whoever fills this page",
        )
        if found.is_usable:
            notes.append(Note(str(found.value), Provenance(found.sources, found.confidence)))
        elif found.question is not None:
            questions.append(found.question)
    return notes, questions


# Regex syntax in a success URL: fill.js matches it as plain text, so such values are dropped.
_REGEX_MARKS = ("\\", "^", "$", "(", "[", "*", "+", "?")


def _plain_success(success: Mapping[str, Any]) -> SuccessSignal:
    url = str(success.get("url_matches", ""))
    return SuccessSignal(
        url_matches="" if any(mark in url for mark in _REGEX_MARKS) else url,
        text_appears=str(success.get("text_appears", "")),
    )


def merge_submit(data: MergeInput) -> tuple[SubmitSpec | None, list[Question]]:
    """Merge the submit control from the analysis and the probe.

    The selector is read from markup, so it counts as extracted. The analysis's
    `inferred` flag covers only the success signal, which is dropped and asked about
    when it was deduced.

    Args:
        data: The merge input.

    Returns:
        (submit, questions).
    """
    raw = data.analysis.get("submit") or {}
    probe = data.probe
    page_selector = probe.submit_selector if probe and probe.submit_selector else MISSING
    found = assess_fact(
        data.skill,
        "submit:selector",
        raw.get("selector") or MISSING,
        Source.EXTRACTED,
        page_value=page_selector,
        answers=data.answers,
        same=lambda _a, _b: True,
        label="the submit control",
    )
    questions = [found.question] if found.question else []
    if not found.is_usable:
        return None, questions
    signal = _plain_success(raw.get("success") or {})
    if signal != SuccessSignal():
        success = assess_fact(
            data.skill,
            "submit:success",
            describe_success(signal),
            _source_of(raw),
            answers=data.answers,
            label="how success shows",
        )
        questions += [success.question] if success.question else []
        if not success.is_usable:
            signal = SuccessSignal()
    label = (probe.submit_label if probe and probe.submit_label else "") or str(
        raw.get("label", "")
    )
    return SubmitSpec(selector=str(found.value), label=label, success=signal), questions


def describe_success(signal: SuccessSignal) -> str:
    """Write a success signal in words, for a question.

    Args:
        signal: The signal.

    Returns:
        Text such as "the URL contains /done".
    """
    parts = [
        f"the URL contains {signal.url_matches}" if signal.url_matches else "",
        f"the page shows {signal.text_appears!r}" if signal.text_appears else "",
    ]
    return " and ".join(part for part in parts if part)


def collect_evidence(analysis: AnalysisDocument) -> list[Evidence]:
    """Turn the analysis's evidence entries into evidence records.

    Args:
        analysis: The page analysis.

    Returns:
        Evidence for fields and rules.
    """
    records = []
    for kind, items, key in (
        ("field", analysis.get("fields", []), "key"),
        ("rule", analysis.get("rules", []), ""),
    ):
        for index, item in enumerate(items, start=1):
            subject = f"{kind}:{item.get(key) if key else index}"
            for found in item.get("evidence", []):
                location = (
                    f"{found['file']}:{found['line']}" if found.get("line") else str(found["file"])
                )
                records.append(
                    Evidence(subject, _source_of(item), location, str(found.get("quote", "")))
                )
    return records


def _sections(analysis: AnalysisDocument, fields: Sequence[FieldSpec]) -> tuple[Section, ...]:
    used = {spec.section for spec in fields}
    return tuple(
        Section(str(s["id"]), str(s.get("label", "")))
        for s in analysis.get("sections", [])
        if s["id"] in used
    )


def _groups(analysis: AnalysisDocument) -> tuple[RepeatGroup, ...]:
    return tuple(
        RepeatGroup(
            str(g["id"]),
            str(g.get("label", "")),
            str(g["row_selector"]),
            str(g["add_selector"]),
            int(g.get("min_rows", 0)),
        )
        for g in analysis.get("groups", [])
    )


def _params(data: MergeInput) -> tuple[RouteParam, ...]:
    described = {str(p["name"]): str(p.get("means", "")) for p in data.analysis.get("params", [])}
    names = list(dict.fromkeys([*find_route_params(data.route), *described]))
    return tuple(RouteParam(name, described.get(name, "")) for name in names)


def _analysis_questions(data: MergeInput) -> list[Question]:
    return [
        Question(
            make_question_id(data.skill, f"note:{index}"),
            data.skill,
            f"note:{index}",
            str(item["text"]),
            answer=data.answers.get(f"note:{index}", ""),
        )
        for index, item in enumerate(data.analysis.get("questions", []), start=1)
    ]


def is_page_verified(fields: Sequence[FieldSpec], probe: ProbedPage | None) -> bool:
    """Tell whether every required field was proven on the running page.

    Args:
        fields: The merged fields.
        probe: The probe result.

    Returns:
        True only when a probe ran and proved each required field's strategy.
    """
    if probe is None:
        return False
    proven = {probed.key for probed in probe.fields if probed.is_proven}
    return all(spec.key in proven for spec in fields if spec.is_required)


# Clicks that change data or leave the page. An open step must only reveal the form,
# so a step naming one of these is never trusted without the developer's yes.
_RISKY_STEP = re.compile(
    r"\b(submit|save|delete|remove|publish|log ?out|sign ?out)\b|type=.?submit", re.IGNORECASE
)


def is_risky_step(step: str) -> bool:
    """Whether an open step looks like a click that changes data or leaves the page.

    Args:
        step: A CSS selector or `text:Label`.

    Returns:
        True when the step names such a click.
    """
    return bool(_RISKY_STEP.search(step))


def _parse_steps(answer: str) -> tuple[str, ...]:
    return tuple(step.strip() for step in answer.split(";") if step.strip())


def find_open_candidates(analysis: dict[str, Any]) -> tuple[str, ...]:
    """Return the analysis's open steps that are safe to try in a browser.

    A deduced step is not trusted in a skill, but `--xy` may try it: if the fields
    appear after the clicks, the browser has proved it. A step that could change data
    is never tried.

    Args:
        analysis: The page analysis.

    Returns:
        The steps, or none when there are none or any of them looks risky.
    """
    raw = analysis.get("open") or {}
    steps = tuple(str(step).strip() for step in raw.get("steps", []) if str(step).strip())
    return () if any(is_risky_step(step) for step in steps) else steps


def merge_open_steps(data: MergeInput) -> tuple[tuple[str, ...], list[Question]]:
    """Decide what to click before the form shows, from the code analysis.

    The steps are a fact like any other: read plainly in the code they are trusted;
    deduced, or naming a click that could change data, they become a question.

    Args:
        data: The merge input.

    Returns:
        (the open steps, or none; questions).
    """
    raw = data.analysis.get("open") or {}
    steps = tuple(str(step).strip() for step in raw.get("steps", []) if str(step).strip())
    if not steps:
        return (), []
    risky = any(is_risky_step(step) for step in steps)
    found = assess_fact(
        data.skill,
        "open",
        steps,
        Source.CLAUDE_INFERRED if risky else _source_of(raw),
        answers=data.answers,
        parse=_parse_steps,
        label="what to click to show the form (separate several clicks with ;)",
    )
    usable = tuple(found.value) if found.is_usable and found.value else ()
    return usable, [found.question] if found.question else []


def find_view_candidates(analysis: Mapping[str, Any], field_keys: set[str]) -> tuple[View, ...]:
    """Return the analysis's views that can be walked, in order.

    Each view is reached from the one before, so the list stops at the first view that
    cannot be walked: no click to reach it, no known field, or a click that could
    change data or leave the page. A field already shown by an earlier view stays there.

    Args:
        analysis: The page analysis.
        field_keys: The keys of the fields kept on the page.

    Returns:
        The views, in fill order.
    """
    views: list[View] = []
    seen: set[str] = set()
    for raw in analysis.get("views") or []:
        view = view_from_dict(raw)
        keys = tuple(key for key in view.keys if key in field_keys and key not in seen)
        clicks = (*view.enter, *view.leave)
        if not keys or not view.enter or any(is_risky_step(step) for step in clicks):
            break
        seen.update(keys)
        views.append(replace(view, keys=keys))
    return tuple(views)


def describe_views(views: Sequence[View]) -> tuple[str, ...]:
    """Write views briefly for a question: name, then the clicks that reach it.

    Args:
        views: The views.

    Returns:
        One line per view.
    """
    return tuple(f"{view.name} (click {', '.join(view.enter)})" for view in views)


def merge_views(data: MergeInput, field_keys: set[str]) -> tuple[tuple[View, ...], list[Question]]:
    """Decide which parts of the form show only after clicks, from the code analysis.

    Read plainly in the code they are trusted; deduced, they become a question. A
    deduced view can still be proven by `--xy`: its fields appearing after the clicks.

    Args:
        data: The merge input.
        field_keys: The keys of the fields kept on the page.

    Returns:
        (the trusted views, questions).
    """
    candidates = find_view_candidates(data.analysis, field_keys)
    if not candidates:
        return (), []
    raw_views = list(data.analysis.get("views") or [])[: len(candidates)]
    is_deduced = any(bool(raw.get("inferred")) for raw in raw_views)
    found = assess_fact(
        data.skill,
        "views",
        describe_views(candidates),
        Source.CLAUDE_INFERRED if is_deduced else Source.EXTRACTED,
        answers=data.answers,
        parse=lambda _: None,
        label="the form's steps, tabs and dialogs, and what to click to reach each",
    )
    usable = candidates if found.is_usable and found.value else ()
    return usable, [found.question] if found.question else []


def build_page_model(data: MergeInput) -> MergeResult:
    """Merge everything known about a route into its page model.

    Args:
        data: The merge input.

    Returns:
        The page model, open questions and evidence.
    """
    fields, field_questions = merge_fields(data)
    open_steps, open_questions = merge_open_steps(data)
    views, view_questions = merge_views(data, {spec.key for spec in fields})
    gotchas, gotcha_questions = merge_gotchas(data)
    rules, rule_questions = merge_rules(data)
    submit, submit_questions = merge_submit(data)
    title = (
        str(data.analysis.get("title", ""))
        or (data.probe.title if data.probe else "")
        or data.route
    )
    page = PageModel(
        route=data.route,
        skill=data.skill,
        title=title,
        app_name=data.app_name,
        app_url=data.app_url,
        fields=tuple(fields),
        purpose=str(data.analysis.get("purpose", "")),
        sections=_sections(data.analysis, fields),
        groups=_groups(data.analysis),
        submit=submit,
        rules=tuple(rules),
        gotchas=tuple(gotchas),
        params=_params(data),
        is_verified=is_page_verified(fields, data.probe),
        source_commit=data.source_commit,
        version=data.version,
        layout=build_layout(fields, data.probe),
        open_steps=open_steps,
        views=views,
    )
    questions = [
        *field_questions,
        *view_questions,
        *open_questions,
        *gotcha_questions,
        *rule_questions,
        *submit_questions,
        *_analysis_questions(data),
    ]
    return MergeResult(page, tuple(questions), tuple(collect_evidence(data.analysis)))
