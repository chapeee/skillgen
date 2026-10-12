"""Confidence arithmetic for facts (spec section 9).

Agreeing sources combine as 1 − (1 − a)(1 − b). Disagreeing sources cap a fact at
0.5 and raise a question. Facts at 0.7 or above go into a skill.
"""

from __future__ import annotations

from collections.abc import Iterable

from skillgen.model.facts import Source

BASE_CONFIDENCE: dict[Source, float] = {
    Source.RUNTIME_PROBED: 0.90,
    Source.EXTRACTED: 0.85,
    Source.CLAUDE_INFERRED: 0.60,
    Source.DEVELOPER_CONFIRMED: 1.00,
    Source.USER_DEFINED: 1.00,
}

INCLUSION_THRESHOLD = 0.7
CONFLICT_CAP = 0.5


def combine_confidence(values: Iterable[float]) -> float:
    """Combine the confidences of sources that agree on a fact.

    Args:
        values: Confidence of each agreeing source, each between 0 and 1.

    Returns:
        The combined confidence, rounded to three decimals; 0.0 for no values.

    Raises:
        ValueError: If a value is outside 0..1.
    """
    remaining_doubt = 1.0
    has_value = False
    for value in values:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"confidence {value} is outside 0..1")
        remaining_doubt *= 1.0 - value
        has_value = True
    if not has_value:
        return 0.0
    return round(1.0 - remaining_doubt, 3)


def score_sources(sources: Iterable[Source]) -> float:
    """Return the confidence of a fact that the given sources all agree on.

    Args:
        sources: The sources that stated the same value.

    Returns:
        The combined confidence of the distinct sources.
    """
    distinct = set(sources)
    return combine_confidence(BASE_CONFIDENCE[source] for source in distinct)


def cap_conflict(confidence: float) -> float:
    """Cap the confidence of a fact whose sources disagree.

    Args:
        confidence: The confidence before the conflict was found.

    Returns:
        The confidence, at most `CONFLICT_CAP`.
    """
    return min(confidence, CONFLICT_CAP)


def is_confident(confidence: float) -> bool:
    """Tell whether a fact is confident enough to go into a skill.

    Args:
        confidence: The fact's confidence.

    Returns:
        True when the confidence reaches `INCLUSION_THRESHOLD`.
    """
    return confidence >= INCLUSION_THRESHOLD
