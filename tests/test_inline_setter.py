"""Tests for the inline setter `SKILL.md` carries instead of pointing at fill.js."""

import json
import re
import threading
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest

from skillgen import TOOL_NAME
from skillgen.assets import read_fill_engine
from skillgen.generate.fill_script import build_fill_script, find_forbidden_syntax
from skillgen.generate.inline_setter import (
    MAX_LANDMARKS,
    STRATEGY_CODES,
    build_field_map,
    build_geometry,
    build_inline_setter,
    build_locate_call,
    build_open_script,
    build_probe_call,
    build_rerun_call,
    choose_landmarks,
    field_selector,
    find_steady_key,
    flatten_values,
    has_manual_fields,
    render_engine,
    store_name,
)
from skillgen.model.page import Box, Condition, Layout, Operator, Strategy, ValueType
from tests.conftest import launch_chromium
from tests.helpers import (
    BENCH,
    load_bench_page,
    load_script,
    load_wizard_page,
    make_field,
    make_page,
)


def test_strategy_codes_cover_every_strategy():
    assert set(STRATEGY_CODES) == set(Strategy)


def test_strategy_codes_are_distinct_single_letters():
    codes = list(STRATEGY_CODES.values())
    assert len(set(codes)) == len(codes)
    assert all(len(code) == 1 for code in codes)


def test_render_engine_is_es2019_only():
    assert find_forbidden_syntax(render_engine()) == []


def test_render_engine_substitutes_its_constants():
    engine = render_engine()
    assert "SEP" not in engine
    assert "sleep(WAIT)" not in engine


def test_build_field_map_keeps_fill_order():
    page = load_bench_page()
    assert [row[0] for row in build_field_map(page)] == [spec.key for spec in page.fields]


def test_build_field_map_orders_country_before_region():
    keys = [row[0] for row in build_field_map(load_bench_page())]
    assert keys.index("country") < keys.index("region")


def test_build_field_map_flags_fields_whose_options_load_late():
    waits = [row[0] for row in build_field_map(load_bench_page()) if len(row) > 3]
    assert "region" in waits


def test_build_field_map_carries_one_code_per_field():
    for row in build_field_map(load_bench_page()):
        assert row[2] in set(STRATEGY_CODES.values())


def test_field_selector_prefixes_a_group_row():
    page = load_bench_page()
    assert field_selector(page, "references[].name").startswith(".reference-row ")


def test_field_selector_leaves_a_plain_field_alone():
    page = load_bench_page()
    assert field_selector(page, "email") == "#email"


def test_field_selector_returns_empty_for_an_unknown_key():
    assert field_selector(load_bench_page(), "not_a_field") == ""


def test_flatten_values_keeps_plain_keys():
    page = load_bench_page()
    assert flatten_values(page, {"email": "alex@example.com"}) == {"email": "alex@example.com"}


def test_flatten_values_moves_the_first_row_onto_flat_keys():
    page = load_bench_page()
    flat = flatten_values(page, {"references": [{"name": "Ray Example"}]})
    assert flat == {"references[].name": "Ray Example"}


def test_flatten_values_drops_rows_after_the_first():
    page = load_bench_page()
    flat = flatten_values(page, {"references": [{"name": "First"}, {"name": "Second"}]})
    assert flat == {"references[].name": "First"}


def test_build_inline_setter_is_one_expression_with_five_arguments():
    page = load_bench_page()
    call = build_inline_setter(page, {"email": "alex@example.com"})
    assert call.startswith("await (async function (S, M, G, V, O) {")
    assert call.rstrip().endswith(")")
    assert '"email":"alex@example.com"' in call
    assert call.split("})(\n", 1)[1].startswith('"bench-apply"')


def test_build_inline_setter_stays_under_half_the_script_it_replaces():
    page = load_bench_page()
    call = build_inline_setter(page, {"email": "alex@example.com"})
    script = build_fill_script(page, read_fill_engine())
    assert len(call.encode("utf-8")) < len(script.encode("utf-8")) / 2


def test_build_inline_setter_without_a_layout_costs_what_it_did_before_the_check():
    page = replace(load_bench_page(), layout=None)
    call = build_inline_setter(page, {"email": "alex@example.com"})
    assert len(call.encode("utf-8")) < 6000


def call_arguments(call: str) -> list[Any]:
    """Read the five arguments back out of a generated call.

    Any: each argument is whatever JSON value the call was built with.
    """
    tail = call.split("})(\n", 1)[1].rsplit("\n)", 1)[0]
    return [json.loads(part) for part in tail.split(",\n")]


def test_build_inline_setter_names_every_field_of_the_page():
    page = load_bench_page()
    _, field_map, _, _, _ = call_arguments(build_inline_setter(page, {}))
    assert [row[0] for row in field_map] == [spec.key for spec in page.fields]


def test_build_inline_setter_passes_null_geometry_without_a_layout():
    page = replace(load_bench_page(), layout=None)
    call = build_inline_setter(page, {})
    _, _, geometry, _, options = call_arguments(call)
    assert geometry is None and options == {}
    assert "function verify()" not in call


def test_build_inline_setter_checks_the_layout_when_there_is_one():
    page = load_bench_page()
    call = build_inline_setter(page, {})
    _, _, geometry, _, _ = call_arguments(call)
    assert geometry is not None
    assert "function verify()" in call


def test_store_name_derives_from_the_tool_name():
    assert store_name() == f"__{TOOL_NAME}"


@pytest.mark.parametrize("has_checks", [False, True])
@pytest.mark.parametrize("has_manual", [False, True])
def test_render_engine_variants_are_es2019_and_fully_substituted(has_checks, has_manual):
    engine = render_engine(has_checks, has_manual)
    assert find_forbidden_syntax(engine) == []
    assert not re.search(r"__[A-Z][A-Z_]*__", engine)


def test_render_engine_without_a_layout_or_manual_fields_leaves_out_measuring():
    engine = render_engine(has_checks=False, has_manual=False)
    assert "function verify()" not in engine
    assert "function locate(" not in engine
    assert "function find(" not in engine


def test_render_engine_with_manual_fields_exposes_locate():
    engine = render_engine(has_checks=False, has_manual=True)
    assert "function locate(" in engine
    assert "run: run, locate: locate" in engine


def test_render_engine_with_checks_refuses_to_fill_a_changed_or_blocked_page():
    engine = render_engine(has_checks=True)
    assert "'changed' || report.layout.state === 'blocked'" in engine
    assert "options.verify === false" in engine


def test_has_manual_fields_spots_a_file_field():
    assert has_manual_fields(load_bench_page())
    assert not has_manual_fields(make_page([make_field("email")]))


def stacked(*keys: str, gap: int = 80) -> Layout:
    """A layout with one field per row, `gap` pixels apart."""
    boxes = tuple((key, Box(100, 100 + index * gap, 300, 40)) for index, key in enumerate(keys))
    return Layout(viewport_width=1280, viewport_height=900, boxes=boxes)


def test_choose_landmarks_returns_nothing_without_a_layout():
    assert choose_landmarks(make_page([make_field("a")])) == []


def test_choose_landmarks_needs_at_least_three_rows():
    page = make_page([make_field("a"), make_field("b")], layout=stacked("a", "b"))
    assert choose_landmarks(page) == []


def test_choose_landmarks_keeps_one_field_per_row():
    fields = [make_field(key) for key in ("a", "b", "c", "d")]
    boxes = (
        ("a", Box(100, 100, 300, 40)),
        ("b", Box(420, 100, 300, 40)),
        ("c", Box(100, 180, 300, 40)),
        ("d", Box(100, 260, 300, 40)),
    )
    page = make_page(fields, layout=Layout(1280, 900, boxes))
    assert [key for key, _ in choose_landmarks(page)] == ["a", "c", "d"]


def test_choose_landmarks_thins_to_the_maximum_keeping_first_and_last():
    keys = [f"field_{index}" for index in range(20)]
    page = make_page([make_field(key) for key in keys], layout=stacked(*keys))
    chosen = [key for key, _ in choose_landmarks(page)]
    assert len(chosen) == MAX_LANDMARKS
    assert chosen[0] == keys[0] and chosen[-1] == keys[-1]


def test_choose_landmarks_skips_conditional_grouped_and_manual_fields():
    condition = Condition(field="a", operator=Operator.FILLED)
    fields = [
        make_field("a"),
        make_field("shown_later", visible_if=condition),
        make_field("row_item", group="rows"),
        make_field("upload", strategy=Strategy.FILE),
        make_field("b"),
        make_field("c"),
    ]
    keys = ("a", "shown_later", "row_item", "upload", "b", "c")
    page = make_page(fields, layout=stacked(*keys))
    assert [key for key, _ in choose_landmarks(page)] == ["a", "b", "c"]


def test_build_geometry_measures_from_the_first_landmark():
    keys = ("a", "b", "c")
    page = make_page([make_field(key) for key in keys], layout=stacked(*keys, gap=90))
    geometry = build_geometry(page)
    assert geometry is not None
    assert geometry["a"] == "a"
    assert geometry["b"] == [["a", 0, 0, 300, 40], ["b", 0, 90, 300, 40], ["c", 0, 180, 300, 40]]
    assert (geometry["w"], geometry["h"]) == (1280, 900)


def test_build_geometry_is_none_without_enough_landmarks():
    assert build_geometry(make_page([make_field("a")])) is None


def test_build_rerun_call_checks_the_layout_by_default():
    call = build_rerun_call(load_bench_page())
    assert call == f'await window["__{TOOL_NAME}"]["bench-apply"].run({{...}})'


def test_build_rerun_call_can_skip_the_check():
    call = build_rerun_call(load_bench_page(), should_skip_check=True)
    assert call.endswith('.run({...}, {"verify": false})')


def test_build_locate_call_names_the_field():
    call = build_locate_call(load_bench_page(), "id_document")
    assert call == f'window["__{TOOL_NAME}"]["bench-apply"].locate("id_document")'


def test_render_engine_opens_the_form_only_with_open_steps():
    assert "openForm" not in render_engine()
    engine = render_engine(open_steps=("#settings",), first_key="email")
    assert "await openForm();" in engine
    assert find_forbidden_syntax(engine) == []
    assert not re.search(r"__[A-Z][A-Z_]*__", engine)


def test_render_engine_clicks_open_steps_only_while_the_form_is_hidden():
    engine = render_engine(open_steps=("#settings",), first_key="email")
    assert 'var first = find("email")' in engine
    assert "if (first && rectOf(first)) { return; }" in engine


def test_build_open_script_is_es2019_and_reports_each_step():
    script = build_open_script()
    assert find_forbidden_syntax(script) == []
    assert script.startswith("async function (steps)")
    assert "'missing'" in script and "'clicked'" in script


def test_find_steady_key_skips_conditional_and_manual_fields():
    condition = Condition(field="a", operator=Operator.FILLED)
    fields = [
        make_field("upload", strategy=Strategy.FILE),
        make_field("later", visible_if=condition),
        make_field("name"),
    ]
    assert find_steady_key(make_page(fields)) == "name"


def test_build_inline_setter_carries_the_pages_open_steps():
    page = replace(load_bench_page(), open_steps=('button[title="Page settings"]',))
    assert '["button[title=\\"Page settings\\"]"]' in build_inline_setter(page, {})


# --- views: steps, tabs and dialogs


def test_wizard_page_has_its_views_in_order():
    page = load_wizard_page()
    assert [view.name for view in page.views] == [
        "Address tab",
        "Step 2",
        "Contact dialog",
        "Step 3",
    ]


def test_render_engine_walks_views_only_when_there_are_some():
    page = load_wizard_page()
    with_views = render_engine(views=page.views, error_selector="[aria-invalid=true]")
    assert "async function walk(" in with_views and "__" not in with_views.replace("__skillgen", "")
    assert "async function walk(" not in render_engine()
    assert find_forbidden_syntax(with_views) == []


def test_build_probe_call_reaches_a_view_without_checking_the_layout():
    call = build_probe_call(load_wizard_page(), {"first_name": "Ada"}, "Step 2")
    assert not call.startswith("await ")
    assert call.rstrip().endswith('{"verify":false,"view":"Step 2"}\n)')


def test_choose_landmarks_ignores_fields_in_views():
    page = load_wizard_page()
    boxes = tuple(
        (spec.key, Box(100, 100 + index * 60, 300, 32)) for index, spec in enumerate(page.fields)
    )
    measured = replace(page, layout=Layout(1280, 900, boxes))
    assert {key for key, _ in choose_landmarks(measured)} <= {"first_name", "last_name"}


@pytest.fixture(scope="module")
def wizard_page() -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    serve = load_script(BENCH / "serve.py")
    server = serve.make_server("127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_api.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        page.url_base = f"http://localhost:{server.server_address[1]}/wizard"
        yield page
        browser.close()
    server.shutdown()


WIZARD_VALUES = {
    "first_name": "Ada",
    "last_name": "Example",
    "city": "Sampletown",
    "department": "Engineering",
    "work_location": "Remote",
    "laptop": "Sample laptop",
    "contact_name": "Sam Example",
    "agree": True,
}


def run_setter(page: Any, values: dict[str, Any], options: dict[str, Any] | None = None) -> Any:
    call = build_inline_setter(load_wizard_page(), values, options).removeprefix("await ")
    return json.loads(page.evaluate(call))


@pytest.mark.browser
def test_setter_walks_tabs_steps_and_a_dialog_in_one_call(wizard_page):
    wizard_page.goto(wizard_page.url_base)
    report = run_setter(wizard_page, WIZARD_VALUES)
    assert report["fill"] == dict.fromkeys(WIZARD_VALUES, "ok")
    assert report["view"] == "Step 3" and "stopped" not in report
    state = wizard_page.evaluate("wizardState()")
    assert state["step"] == 3 and state["submitted"] is False
    assert (state["city"], state["laptop"], state["contact_name"]) == (
        "Sampletown",
        "Sample laptop",
        "Sam Example",
    )


@pytest.mark.browser
def test_setter_stops_where_the_page_will_not_move_on(wizard_page):
    wizard_page.goto(wizard_page.url_base)
    report = run_setter(wizard_page, {"last_name": "Example", "department": "Sales"})
    assert report["stopped"]["view"] == "Step 2"
    assert "First name is required" in report["stopped"]["errors"]
    assert report["fill"] == {"last_name": "ok", "department": "escalate"}


@pytest.mark.browser
def test_setter_reports_fields_behind_the_current_part(wizard_page):
    wizard_page.goto(wizard_page.url_base)
    run_setter(wizard_page, {"first_name": "Ada"}, {"view": "Step 2"})
    report = run_setter(wizard_page, {"first_name": "Grace", "department": "Sales"})
    assert report["fill"] == {"first_name": "escalate", "department": "ok"}
    assert report["view"] == "Step 2"


@pytest.mark.browser
def test_setter_trusts_the_clicks_of_a_part_it_cannot_check(wizard_page):
    page = load_wizard_page()
    broken = replace(
        page,
        fields=tuple(
            replace(spec, selector="#contact_{idx}_name") if spec.key == "contact_name" else spec
            for spec in page.fields
        ),
    )
    wizard_page.goto(wizard_page.url_base)
    call = build_inline_setter(broken, WIZARD_VALUES).removeprefix("await ")
    report = json.loads(wizard_page.evaluate(call))
    assert report["fill"]["contact_name"] == "escalate"
    assert report["fill"]["agree"] == "ok" and report["view"] == "Step 3"


# A framework-controlled form in miniature: the element's own `value` setter is wrapped
# to remember what was written, and an input event carrying that same value is ignored;
# the box's state follows clicks only. A direct `el.value = …` leaves the state empty
# while the page shows the value.
CONTROLLED_FORM = """
<input id="title"><input id="agree" type="checkbox">
<script>
  var state = { title: '', agree: false }, last = '';
  var input = document.getElementById('title');
  var own = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  Object.defineProperty(input, 'value', {
    get: function () { return own.get.call(this); },
    set: function (value) { last = String(value); own.set.call(this, value); }
  });
  input.addEventListener('input', function () {
    if (input.value !== last) { last = input.value; state.title = input.value; }
  });
  var box = document.getElementById('agree');
  box.addEventListener('click', function () { state.agree = box.checked; });
  window.formState = function () { return state; };
</script>
"""


@pytest.mark.browser
def test_setter_fills_inputs_a_framework_controls(wizard_page):
    page = make_page([make_field("title"), make_field("agree", value_type=ValueType.BOOLEAN)])
    wizard_page.set_content(CONTROLLED_FORM)
    call = build_inline_setter(page, {"title": "Ada", "agree": True}).removeprefix("await ")
    report = json.loads(wizard_page.evaluate(call))
    assert report["fill"] == {"title": "ok", "agree": "ok"}
    assert wizard_page.evaluate("formState()") == {"title": "Ada", "agree": True}
