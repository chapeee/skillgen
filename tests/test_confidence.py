import pytest

from skillgen.model.confidence import (
    BASE_CONFIDENCE,
    cap_conflict,
    combine_confidence,
    is_confident,
    score_sources,
)
from skillgen.model.facts import Source


def test_combine_confidence_matches_spec_example():
    # Spec section 9: code plus probe gives 0.985.
    assert combine_confidence([0.85, 0.90]) == 0.985


def test_combine_confidence_returns_zero_for_no_values():
    assert combine_confidence([]) == 0.0


def test_combine_confidence_rejects_out_of_range():
    with pytest.raises(ValueError, match="outside"):
        combine_confidence([1.5])


def test_score_sources_ignores_repeated_sources():
    assert score_sources([Source.EXTRACTED, Source.EXTRACTED]) == BASE_CONFIDENCE[Source.EXTRACTED]


def test_score_sources_developer_confirmed_is_certain():
    assert score_sources([Source.CLAUDE_INFERRED, Source.DEVELOPER_CONFIRMED]) == 1.0


def test_cap_conflict_caps_at_half():
    assert cap_conflict(0.985) == 0.5
    assert cap_conflict(0.3) == 0.3


def test_is_confident_uses_threshold():
    assert is_confident(0.7)
    assert not is_confident(0.6)
