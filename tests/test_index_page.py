import json

from skillgen.assets import read_index_template
from skillgen.generate.index_page import (
    IndexInput,
    build_graph,
    build_index_data,
    layout_graph,
    render_index_html,
)
from skillgen.model.route import RouteEntry
from tests.helpers import load_bench_page


def make_input():
    page = load_bench_page()
    routes = (
        RouteEntry("/apply", page.skill, has_form=True),
        RouteEntry("/", "bench-home", has_form=False),
    )
    return IndexInput(
        app_name="Bench",
        pages=(page,),
        routes=routes,
        skill_sizes={page.skill: 8000},
        commit="abc123",
        generated_on="2026-10-08",
        detected=("nextjs-app",),
        changed=(page.skill,),
    )


def test_build_graph_links_skills_sections_fields_and_dependencies():
    nodes, links = build_graph([load_bench_page()], "Bench")
    kinds = {node["kind"] for node in nodes}
    assert kinds == {"app", "skill", "section", "field"}
    assert any(link["kind"] == "dependency" for link in links)
    assert any(link["kind"] == "condition" for link in links)


def test_layout_graph_is_deterministic_and_in_bounds():
    first, links = build_graph([load_bench_page()], "Bench")
    second, _ = build_graph([load_bench_page()], "Bench")
    layout_graph(first, links)
    layout_graph(second, links)
    assert first == second
    assert all(40 <= node["x"] <= 960 and 40 <= node["y"] <= 960 for node in first)


def test_build_index_data_counts_and_cards():
    document = build_index_data(make_input())
    assert document["numbers"] == {
        "routes": 2,
        "skills": 1,
        "fields": 21,
        "dependencies": 6,
        "verified": 0,
    }
    card = document["skills"][0]
    assert card["changed"] and card["has_rows"] and card["skill_tokens"] == 2000
    assert document["no_form"] == ["/"]


def test_render_index_html_is_self_contained_and_escapes_script():
    data = build_index_data(make_input())
    data["app"] = "</script><b>"
    page = render_index_html(data, read_index_template())
    assert "<script src" not in page and "<link" not in page
    assert "<\\/script>" in page
    payload = page.split("var data = ", 1)[1].split(", focus = null", 1)[0]
    assert json.loads(payload.replace("<\\/", "</"))["app"] == "</script><b>"
