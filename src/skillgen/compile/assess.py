"""Decide one fact: combine code, probe and developer answers into a value and confidence.

A fact here is one attribute of one subject, such as the `required` flag of a field.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from skillgen.model.confidence import cap_conflict, is_confident, score_sources
from skillgen.model.facts import Source
from skillgen.model.route import Question

YES_ANSWERS = frozenset({"yes", "y", "true", "keep", "confirm", "correct", "code"})
NO_ANSWERS = frozenset({"no", "n", "false", "drop", "remove", "wrong"})
PAGE_ANSWERS = frozenset({"page", "probe"})


class _Missing:
    """Marks a source that said nothing about a fact."""

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()


@dataclass(frozen=True)
class Assessment:
    """The outcome for one fact.

    Attributes:
        value: The chosen value; None when the fact was dropped.
        sources: Sources that support the value.
        confidence: Combined confidence.
        question: A question for the developer, when one is needed.
        is_dropped: True when the developer said the fact is wrong.
    """

    value: Any
    sources: tuple[Source, ...]
    confidence: float
    question: Question | None = None
    is_dropped: bool = False

    @property
    def is_usable(self) -> bool:
        """True when the fact may go into a skill."""
        return not self.is_dropped and self.value is not None and is_confident(self.confidence)


def make_question_id(skill: str, subject: str) -> str:
    """Build a short, stable question id.

    Args:
        skill: The skill name.
        subject: The fact's subject.

    Returns:
        An id such as `q3f9a1c`.
    """
    return "q" + hashlib.sha1(f"{skill}|{subject}".encode()).hexdigest()[:6]


def describe_value(value: Any) -> str:
    """Write a fact's value briefly for a question.

    Args:
        value: Any JSON-like value.

    Returns:
        Short text.
    """
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return " · ".join(str(item) for item in value) or "(empty)"
    return str(value)


def apply_answer(
    answer: str, claimed: Any, page_value: Any, parse: Callable[[str], Any]
) -> Assessment:
    """Turn a developer's answer into a confirmed fact.

    Args:
        answer: The answer text.
        claimed: The value the code claimed.
        page_value: The value the probe saw, or MISSING.
        parse: Turns free text into a value for this fact.

    Returns:
        A developer-confirmed assessment, or a dropped one.
    """
    word = answer.strip().lower()
    confirmed = (Source.DEVELOPER_CONFIRMED,)
    if word in NO_ANSWERS:
        return Assessment(None, confirmed, 1.0, is_dropped=True)
    if word in YES_ANSWERS:
        return Assessment(claimed, confirmed, 1.0)
    if word in PAGE_ANSWERS and page_value is not MISSING:
        return Assessment(page_value, confirmed, 1.0)
    return Assessment(parse(answer.strip()), confirmed, 1.0)


def assess_fact(
    skill: str,
    subject: str,
    claimed: Any,
    claimed_source: Source,
    *,
    page_value: Any = MISSING,
    answers: Mapping[str, str] | None = None,
    parse: Callable[[str], Any] = str,
    same: Callable[[Any, Any], bool] = lambda a, b: a == b,
    label: str = "",
    should_keep_claimed: bool = False,
) -> Assessment:
    """Combine what the code claims and what the page showed into one fact.

    Args:
        skill: The skill name, for question ids.
        subject: What the fact is about, such as `field:email:required`.
        claimed: The value the code (via Claude) states; MISSING when it says nothing.
        claimed_source: `EXTRACTED` or `CLAUDE_INFERRED`.
        page_value: The value the probe saw, or MISSING when it did not look.
        answers: Developer answers by subject.
        parse: Turns a free-text answer into a value.
        same: Decides whether the two values agree.
        label: Human-readable name of the fact for questions.
        should_keep_claimed: On agreement keep the code's value (when it is more
            specific than what the page shows), instead of the page's.

    Returns:
        The assessment, with a question when sources disagree or confidence is low.
    """
    answer = (answers or {}).get(subject, "")
    if answer:
        return apply_answer(answer, claimed, page_value, parse)
    what = label or subject
    question_id = make_question_id(skill, subject)
    if claimed is MISSING:
        if page_value is MISSING:
            return Assessment(None, (), 0.0)
        return Assessment(
            page_value, (Source.RUNTIME_PROBED,), score_sources([Source.RUNTIME_PROBED])
        )
    if page_value is MISSING:
        confidence = score_sources([claimed_source])
        question = (
            None
            if is_confident(confidence)
            else Question(
                question_id,
                skill,
                subject,
                f"Is this right? {what}: {describe_value(claimed)}",
                ("yes", "no"),
            )
        )
        return Assessment(claimed, (claimed_source,), confidence, question)
    sources = (claimed_source, Source.RUNTIME_PROBED)
    if same(claimed, page_value):
        agreed = claimed if should_keep_claimed else page_value
        return Assessment(agreed, sources, score_sources(sources))
    text = (
        f"The code and the page disagree on {what}. "
        f"Code: {describe_value(claimed)}. Page: {describe_value(page_value)}."
    )
    question = Question(question_id, skill, subject, text, ("code", "page", "no"))
    return Assessment(claimed, sources, cap_conflict(score_sources(sources)), question)
