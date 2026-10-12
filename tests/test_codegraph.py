import os
from pathlib import Path

import graphify.extract

from skillgen.graph.codegraph import (
    CodeGraph,
    build_source_snapshot_from_paths,
    collapse_extraction,
    find_graph_staleness,
    graph_from_dict,
    graph_to_dict,
    load_code_graph,
    save_code_graph,
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


def test_collapse_extraction_builds_file_graph():
    extraction = {
        "nodes": [
            {"id": "a", "label": "a.ts", "source_file": "a.ts"},
            {"id": "a_f", "label": "f()", "source_file": "a.ts"},
            {"id": "b", "label": "b.ts", "source_file": "b.ts"},
            {"id": "ext", "label": "react"},
        ],
        "edges": [
            {"source": "a", "target": "b", "relation": "imports_from"},
            {"source": "a", "target": "a_f", "relation": "contains"},
            {"source": "a", "target": "ext", "relation": "imports"},
        ],
    }
    graph = collapse_extraction(extraction)
    assert graph.files == ("a.ts", "b.ts")
    assert graph.edges == (("a.ts", "b.ts", "imports_from"),)
    assert graph.symbols == {"f": ("a.ts",)}


def test_code_graph_round_trips(tmp_path):
    assert graph_from_dict(graph_to_dict(GRAPH)) == GRAPH
    save_code_graph(GRAPH, tmp_path / "g.json")
    loaded = load_code_graph(tmp_path / "g.json")
    assert loaded is not None
    graph, built_at = loaded
    assert graph == GRAPH and built_at > 0
    assert load_code_graph(tmp_path / "missing.json") is None


def test_find_graph_staleness_spots_an_edit_a_deletion_and_a_new_file(tmp_path):
    """A cached graph that no longer matches the code is silently wrong, not just old.

    A component then resolves to a file that has moved, or not at all, and the page is
    sliced from the router that declares every route instead.
    """
    (tmp_path / "src").mkdir()
    for name in ("src/a.ts", "src/b.ts"):
        (tmp_path / name).write_text("export const a = 1;", encoding="utf-8")
    graph = CodeGraph(files=("src/a.ts", "src/b.ts"), edges=())
    built_at = 1_000_000.0
    older, newer = built_at - 10, built_at + 10

    def touch(name: str, when: float) -> None:
        os.utime(tmp_path / name, (when, when))

    for name in ("src/a.ts", "src/b.ts", "src"):
        touch(name, older)
    assert find_graph_staleness(graph, tmp_path, built_at) == ""
    assert "recorded build times" in find_graph_staleness(graph, tmp_path, 0.0)
    touch("src/a.ts", newer)
    assert find_graph_staleness(graph, tmp_path, built_at) == "src/a.ts changed"
    touch("src/a.ts", older)
    touch("src", newer)
    assert find_graph_staleness(graph, tmp_path, built_at) == "files were added or removed in src"
    touch("src", older)
    (tmp_path / "src/a.ts").unlink()
    assert find_graph_staleness(graph, tmp_path, built_at) == "src/a.ts is gone"


def test_find_graph_staleness_ignores_generated_root_changes_but_sees_source_additions(
    tmp_path,
):
    """Generated folders change the root mtime without changing the source graph."""
    source = tmp_path / "app.ts"
    source.write_text("export const app = 1;", encoding="utf-8")
    graph = CodeGraph(files=("app.ts",), edges=())
    built_at = 1_000_000.0
    older, newer = built_at - 10, built_at + 10
    os.utime(source, (older, older))

    for folder in (".skillgen", "skills", "dist"):
        (tmp_path / folder).mkdir()
    for name in ("skills-index.html", "skills-index.json"):
        (tmp_path / name).write_text("generated", encoding="utf-8")
    os.utime(tmp_path, (newer, newer))
    excluded = (".skillgen", "skills", "dist", "skills-index.html", "skills-index.json")
    assert find_graph_staleness(graph, tmp_path, built_at, excluded) == ""

    added = tmp_path / "new.ts"
    added.write_text("export const newValue = 1;", encoding="utf-8")
    os.utime(added, (newer, newer))
    assert "files were added or removed" in find_graph_staleness(
        graph, tmp_path, built_at, excluded
    )


def test_snapshot_uses_recognized_inventory_for_empty_and_nested_inputs(tmp_path, monkeypatch):
    """Empty recognized files and new nested folders are part of the cache contract."""
    current: list[Path] = []
    monkeypatch.setattr(graphify.extract, "collect_files", lambda *_args, **_kwargs: current)
    snapshot = build_source_snapshot_from_paths(tmp_path, [], ())
    graph = CodeGraph(files=(), edges=(), source_snapshot=snapshot)
    assert find_graph_staleness(graph, tmp_path, 1.0) == ""

    nested = tmp_path / "new" / "deep" / "page.custom"
    nested.parent.mkdir(parents=True)
    nested.write_text("page", encoding="utf-8")
    current.append(nested)
    reason = find_graph_staleness(graph, tmp_path, 1.0)
    assert "added or removed" in reason


def test_snapshot_detects_ignore_configuration_and_exact_generated_file_exclusions(
    tmp_path, monkeypatch
):
    """Ignore edits invalidate, while excluded generated files do not enter inventory."""
    source = tmp_path / "page.tsx"
    generated = tmp_path / "skills-index.html"
    source.write_text("page", encoding="utf-8")
    generated.write_text("generated", encoding="utf-8")
    current = [source, generated]
    monkeypatch.setattr(graphify.extract, "collect_files", lambda *_args, **_kwargs: current)
    snapshot = build_source_snapshot_from_paths(tmp_path, current, ("skills-index.html",))
    graph = CodeGraph(files=("page.tsx",), edges=(), source_snapshot=snapshot)
    assert find_graph_staleness(graph, tmp_path, 1.0, ("skills-index.html",)) == ""

    (tmp_path / ".graphifyignore").write_text("page.tsx\n", encoding="utf-8")
    assert find_graph_staleness(graph, tmp_path, 1.0, ("skills-index.html",)) == (
        "ignore configuration changed"
    )


def test_snapshot_detects_deletion_even_when_the_collapsed_graph_did_not_emit_the_file(
    tmp_path, monkeypatch
):
    """A recognized source file with no graph node still invalidates on deletion."""
    source = tmp_path / "empty.ts"
    source.write_text("", encoding="utf-8")
    monkeypatch.setattr(graphify.extract, "collect_files", lambda *_args, **_kwargs: [source])
    snapshot = build_source_snapshot_from_paths(tmp_path, [source], ())
    source.unlink()
    monkeypatch.setattr(graphify.extract, "collect_files", lambda *_args, **_kwargs: [])
    graph = CodeGraph(files=(), edges=(), source_snapshot=snapshot)
    assert find_graph_staleness(graph, tmp_path, 1.0) == "empty.ts is gone"


def test_collapse_extraction_keeps_graphify_route_nodes():
    extraction = {
        "nodes": [
            {"id": "page", "label": "Contact.cshtml", "source_file": "Pages/Contact.cshtml"},
            {
                "id": "route_contact",
                "label": "route:/contact",
                "source_file": "Pages/Contact.cshtml",
            },
            {"id": "screen", "label": "home.dart", "source_file": "lib/home.dart"},
            {"id": "route_x", "label": "Route /settings"},
        ],
        "edges": [{"source": "screen", "target": "route_x", "relation": "navigates"}],
    }
    assert collapse_extraction(extraction).routes == (
        ("/contact", "Pages/Contact.cshtml"),
        ("/settings", "lib/home.dart"),
    )
