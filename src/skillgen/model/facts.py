"""Where a fact came from, and the record of evidence kept beside it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Source(str, Enum):
    """Where a fact came from (spec section 9)."""

    RUNTIME_PROBED = "RUNTIME_PROBED"
    EXTRACTED = "EXTRACTED"
    CLAUDE_INFERRED = "CLAUDE_INFERRED"
    DEVELOPER_CONFIRMED = "DEVELOPER_CONFIRMED"
    USER_DEFINED = "USER_DEFINED"


@dataclass(frozen=True)
class Provenance:
    """The sources and confidence attached to one fact.

    Attributes:
        sources: Every source that stated the fact, without duplicates.
        confidence: Combined confidence between 0 and 1.
    """

    sources: tuple[Source, ...]
    confidence: float


@dataclass(frozen=True)
class Evidence:
    """Where a fact was seen. Stays in `.skillgen/`; never reaches a skill.

    Attributes:
        subject: What the evidence is about, such as `field:email.required`.
        source: The source that produced the evidence.
        location: A file and line (`src/pages/Signup.tsx:12`) or a probe capture id.
        detail: Short free text, for example the literal code that was read.
    """

    subject: str
    source: Source
    location: str
    detail: str = ""


def parse_sources(values: list[str]) -> tuple[Source, ...]:
    """Turn source names into `Source` values, keeping order and dropping repeats.

    Args:
        values: Source names such as `"EXTRACTED"`.

    Returns:
        The matching sources, first occurrence first.

    Raises:
        ValueError: If a name is not a known source.
    """
    result: list[Source] = []
    for value in values:
        source = Source(value)
        if source not in result:
            result.append(source)
    return tuple(result)
