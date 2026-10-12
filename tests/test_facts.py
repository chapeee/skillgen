import pytest

from skillgen.model.facts import Source, parse_sources


def test_parse_sources_keeps_order_and_drops_repeats():
    assert parse_sources(["EXTRACTED", "RUNTIME_PROBED", "EXTRACTED"]) == (
        Source.EXTRACTED,
        Source.RUNTIME_PROBED,
    )


def test_parse_sources_rejects_unknown():
    with pytest.raises(ValueError):
        parse_sources(["GUESSED"])
