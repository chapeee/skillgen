from skillgen.graph.codegraph import CodeGraph
from skillgen.graph.slice import (
    find_affected_files,
    find_stale_skills,
    resolve_component,
    slice_page,
)

GRAPH = CodeGraph(
    files=("app.tsx", "page.tsx", "field.tsx", "util.ts", "deep.ts", "sibling.tsx", "package.json"),
    edges=(
        ("app.tsx", "page.tsx", "imports_from"),
        ("app.tsx", "sibling.tsx", "imports_from"),
        ("page.tsx", "field.tsx", "imports_from"),
        ("page.tsx", "package.json", "imports"),
        ("field.tsx", "util.ts", "calls"),
        ("util.ts", "deep.ts", "imports"),
    ),
    symbols={"Page": ("page.tsx",), "Field": ("field.tsx", "other.tsx")},
)
SIZES = dict.fromkeys(GRAPH.files, 400)


def test_slice_page_ranks_by_distance_and_drops_manifests():
    page_slice = slice_page(GRAPH, ["page.tsx"], SIZES, depth=3)
    assert page_slice.files == (("page.tsx", 0), ("field.tsx", 1), ("util.ts", 2), ("deep.ts", 3))


def test_slice_page_keeps_context_without_following_it():
    paths = slice_page(GRAPH, ["page.tsx"], SIZES, context_files=["app.tsx"], depth=1).paths
    assert "app.tsx" in paths and "sibling.tsx" not in paths


def test_slice_page_caps_files_and_tokens():
    assert slice_page(GRAPH, ["page.tsx"], SIZES, max_files=2).is_truncated
    capped = slice_page(GRAPH, ["page.tsx"], SIZES, max_tokens=150)
    assert capped.paths == ("page.tsx",) and capped.is_truncated


def test_find_affected_files_walks_backwards():
    assert find_affected_files(GRAPH, ["util.ts"], depth=2) == {"util.ts", "field.tsx", "page.tsx"}


def test_find_stale_skills():
    assert find_stale_skills({"a": ["page.tsx"], "b": ["x"]}, {"page.tsx"}) == ["a"]


def test_resolve_component_prefers_imported_definition():
    assert resolve_component(GRAPH, "Page", "app.tsx") == "page.tsx"
    assert resolve_component(GRAPH, "Field", "page.tsx") == "field.tsx"
    assert resolve_component(GRAPH, "Field", "app.tsx") is None
    assert resolve_component(GRAPH, "views.Page.as_view()", "x") == "page.tsx"


def test_resolve_component_finds_an_imported_file_named_after_the_component():
    graph = CodeGraph(
        files=("src/router/index.js", "src/views/SignupView.vue", "src/views/Other.vue"),
        edges=(
            ("src/router/index.js", "src/views/SignupView.vue", "imports_from"),
            ("src/router/index.js", "src/views/Other.vue", "imports_from"),
        ),
    )
    found = resolve_component(graph, "SignupView", "src/router/index.js")
    assert found == "src/views/SignupView.vue"
    assert resolve_component(graph, "Missing", "src/router/index.js") is None
