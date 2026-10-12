import json
from dataclasses import replace

import pytest

from skillgen.errors import ModelError
from skillgen.model.page import Box, Layout, Operator, Strategy, ValueType, list_dependencies
from skillgen.model.serialize import (
    box_from_list,
    box_to_list,
    layout_from_dict,
    layout_to_dict,
    page_from_dict,
    page_to_dict,
    viewport_from_list,
)
from skillgen.schema import find_schema_problems
from tests.helpers import BENCH, load_bench_page, load_wizard_page


def test_page_to_dict_round_trips_bench_page():
    page = load_bench_page()
    assert page_from_dict(page_to_dict(page)) == page


def test_page_to_dict_matches_schema():
    assert find_schema_problems(page_to_dict(load_bench_page()), "page") == []


def test_bench_page_json_matches_schema():
    document = json.loads((BENCH / "page.json").read_text(encoding="utf-8"))
    assert find_schema_problems(document, "page") == []


def test_page_from_dict_reads_conditions_and_dependencies():
    page = load_bench_page()
    company = next(spec for spec in page.fields if spec.key == "company_name")
    assert company.visible_if is not None
    assert company.visible_if.operator is Operator.IN
    assert company.visible_if.values == ("Company",)
    links = {(d.source, d.target, d.kind) for d in list_dependencies(page)}
    assert ("country", "region", "options_from") in links


def test_page_from_dict_keeps_fill_order():
    page = load_bench_page()
    assert [spec.key for spec in page.fields][:3] == ["full_name", "email", "username"]


def test_page_from_dict_rejects_unknown_fill_order_key():
    with pytest.raises(ModelError, match="unknown fields"):
        page_from_dict({"route": "/x", "skill": "x", "fields": {}, "fill_order": ["ghost"]})


def test_page_from_dict_rejects_unknown_strategy():
    data = {"route": "/x", "skill": "x", "fields": {"a": {"strategy": "telepathy"}}}
    with pytest.raises(ModelError, match="telepathy"):
        page_from_dict(data)


def test_page_to_dict_omits_defaults():
    data = page_to_dict(load_bench_page())
    assert "required" not in data["fields"]["bio"]
    assert data["fields"]["bio"]["type"] == ValueType.LONG_TEXT.value
    assert data["fields"]["city"]["strategy"] == Strategy.ARIA_COMBOBOX.value
    assert data["verified"] is False


def test_box_round_trips():
    box = Box(left=306, top=180, width=654, height=42)
    assert box_from_list(box_to_list(box)) == box


@pytest.mark.parametrize("data", [None, [], [1, 2, 3], ["a", 1, 2, 3], [0, 0, 0, 0]])
def test_box_from_list_rejects_what_is_not_a_measured_box(data):
    assert box_from_list(data) is None


def test_box_from_list_rounds_fractional_pixels():
    assert box_from_list([306.6, 180.2, 654.5, 42.0]) == Box(307, 180, 654, 42)


@pytest.mark.parametrize(
    ("data", "expected"),
    [([1280, 900], (1280, 900)), ([1280], (1280, 0)), (None, (0, 0)), (["x", 900], (0, 0))],
)
def test_viewport_from_list_falls_back_to_zero(data, expected):
    assert viewport_from_list(data) == expected


def test_layout_round_trips_with_its_provenance():
    layout = Layout(1280, 900, (("email", Box(306, 260, 654, 42)),))
    assert layout_from_dict(layout_to_dict(layout)) == layout


def test_layout_from_dict_drops_malformed_boxes():
    layout = layout_from_dict({"viewport": [1280, 900], "boxes": {"a": [1, 2, 3, 4], "b": [1]}})
    assert layout is not None and [key for key, _ in layout.boxes] == ["a"]


def test_page_with_a_layout_round_trips_and_passes_the_schema():
    layout = Layout(1280, 900, (("email", Box(306, 260, 654, 42)),))
    page = replace(load_bench_page(), layout=layout)
    data = page_to_dict(page)
    assert find_schema_problems(data, "page") == []
    assert page_from_dict(data) == page


def test_page_without_a_layout_writes_no_layout_key():
    assert "layout" not in page_to_dict(replace(load_bench_page(), layout=None))


def test_page_round_trip_keeps_views():
    page = load_wizard_page()
    data = page_to_dict(page)
    assert find_schema_problems(data, "page") == []
    assert data["views"][2] == {
        "name": "Contact dialog",
        "enter": ["text:Add contact"],
        "fields": ["contact_name"],
        "leave": ["text:Done"],
    }
    assert page_from_dict(data).views == page.views
