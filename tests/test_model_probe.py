from skillgen.model.page import Strategy, ValueType
from skillgen.model.probe import ProbedField, ProbedPage


def test_probed_field_defaults_are_conservative():
    probed = ProbedField("a", "A", "#a", Strategy.NATIVE_INPUT, ValueType.TEXT)
    assert probed.is_visible
    assert not (probed.is_proven or probed.is_required or probed.is_repeated)


def test_probed_page_defaults_to_no_empty_submit():
    assert not ProbedPage(url="u", title="t", fields=()).has_empty_submit
