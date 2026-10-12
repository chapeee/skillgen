from dataclasses import replace
from typing import Any

from skillgen.compile.layout import build_layout, carry_layout, find_measured_control
from skillgen.model.page import Box, Strategy, ValueType
from skillgen.model.probe import ProbedField, ProbedPage
from tests.helpers import load_bench_page, make_field

BOX = Box(left=100, top=200, width=300, height=40)


# Any: these are ProbedField keyword arguments of several types, as in make_field.
def make_probed(key: str, selector: str = "", **changes: Any) -> ProbedField:
    base = ProbedField(
        key=key,
        label=key,
        selector=selector or f"#{key}",
        strategy=Strategy.NATIVE_INPUT,
        value_type=ValueType.TEXT,
        box=BOX,
    )
    return replace(base, **changes)


def make_probe(*fields: ProbedField, width: int = 1280, height: int = 900) -> ProbedPage:
    return ProbedPage(
        url="https://demo.example.com/things/new",
        title="New thing",
        fields=fields,
        viewport_width=width,
        viewport_height=height,
    )


def test_build_layout_returns_none_without_a_probe():
    assert build_layout([make_field("email")], None) is None


def test_build_layout_returns_none_when_the_viewport_was_not_measured():
    probe = make_probe(make_probed("email"), width=0)
    assert build_layout([make_field("email")], probe) is None


def test_build_layout_keeps_the_box_and_viewport():
    layout = build_layout([make_field("email")], make_probe(make_probed("email")))
    assert layout is not None
    assert (layout.viewport_width, layout.viewport_height) == (1280, 900)
    assert layout.box_of("email") == BOX


def test_build_layout_skips_a_field_whose_selector_differs_from_the_probes():
    # The box would describe a different element than the one the skill reads back.
    probe = make_probe(make_probed("email", selector="input[name=email]"))
    assert build_layout([make_field("email", selector="#email")], probe) is None


def test_build_layout_skips_fields_in_repeating_rows():
    probe = make_probe(make_probed("item_name"))
    assert build_layout([make_field("item_name", group="items")], probe) is None


def test_build_layout_returns_none_when_nothing_was_measured():
    probe = make_probe(make_probed("email", box=None))
    assert build_layout([make_field("email")], probe) is None


def test_build_layout_keeps_only_measured_fields():
    probe = make_probe(make_probed("email"), make_probed("company", box=None))
    layout = build_layout([make_field("email"), make_field("company")], probe)
    assert layout is not None
    assert [key for key, _ in layout.boxes] == ["email"]


def test_find_measured_control_ignores_repeated_controls():
    probe = make_probe(make_probed("email", is_repeated=True))
    assert find_measured_control(make_field("email"), probe) is None


def test_find_measured_control_matches_on_selector_not_key():
    probe = make_probe(make_probed("other_key", selector="#email"))
    found = find_measured_control(make_field("email"), probe)
    assert found is not None and found.key == "other_key"


def test_carry_layout_keeps_boxes_only_for_unchanged_selectors():
    page = load_bench_page()
    assert page.layout is not None
    measured = dict(page.layout.boxes)
    first, second = [spec for spec in page.fields if spec.key in measured][:2]
    moved = replace(second, selector="#somewhere-else")
    changed = replace(page, fields=tuple(moved if s.key == second.key else s for s in page.fields))
    carried = carry_layout(page, changed)
    assert carried is not None
    keys = dict(carried.boxes)
    assert first.key in keys and second.key not in keys
    assert carry_layout(None, page) is None
