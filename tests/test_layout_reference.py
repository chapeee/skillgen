import json
from dataclasses import replace

from skillgen.generate.inline_setter import build_geometry
from skillgen.generate.layout_reference import render_layout_reference
from skillgen.model.page import Box, Layout
from tests.helpers import load_bench_page, load_wizard_page


def test_render_layout_reference_keeps_every_measured_field():
    page = load_bench_page()
    assert page.layout is not None
    document = json.loads(render_layout_reference(page) or "")
    assert document["viewport"] == {
        "width": page.layout.viewport_width,
        "height": page.layout.viewport_height,
    }
    assert {field["key"] for field in document["fields"]} == {key for key, _ in page.layout.boxes}


def test_render_layout_reference_agrees_with_the_fill_calls_check():
    page = load_bench_page()
    document = json.loads(render_layout_reference(page) or "")
    geometry = build_geometry(page)
    assert geometry is not None and document["anchor"] == geometry["a"]
    by_key = {field["key"]: field for field in document["fields"]}
    for key, dx, dy, width, height in geometry["b"]:  # type: ignore[attr-defined]
        field = by_key[key]
        assert (field["dx"], field["dy"], field["width"], field["height"]) == (
            dx,
            dy,
            width,
            height,
        )
        assert field["landmark"] is True


def test_render_layout_reference_is_nothing_without_a_layout():
    assert render_layout_reference(replace(load_bench_page(), layout=None)) is None


def test_render_layout_reference_names_the_view_each_field_was_measured_in():
    page = load_wizard_page()
    boxes = tuple((spec.key, Box(10, 10 + i * 50, 100, 30)) for i, spec in enumerate(page.fields))
    document = json.loads(
        render_layout_reference(replace(page, layout=Layout(1280, 900, boxes))) or ""
    )
    views = {field["key"]: field.get("view", "") for field in document["fields"]}
    assert views["first_name"] == "" and views["contact_name"] == "Contact dialog"
    assert [view["name"] for view in document["views"]][-1] == "Step 3"
