"""Graphify's own `explain` and `path`, asked through its command line.

These questions are Graphify's, so they are asked of it rather than reimplemented. It
is an aid and never a requirement: when its CLI is missing, fails, times out or has no
answer, a run carries on with the file list it always had.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from skillgen.graph.connections import (
    GRAPH_FILE,
    GRAPHIFY_OUT,
    MAX_ANSWER_LINES,
    GraphifyGraph,
    build_graph,
    explain_node,
    find_graphify_command,
    find_path,
    load_graph_metadata,
)

EXPLAIN = """Node: ClaimForm.vue
  ID:        src_views_claimform
  Source:    src/views/ClaimForm.vue L1
  Degree:    3

Connections (3):
  --> CollapsiblePanel.vue [imports_from] [EXTRACTED] src/views/ClaimForm.vue:L5
  <-- index.js [imports_from] [EXTRACTED] src/router/index.js:L10
"""


class FakeRun:
    """Stands in for `subprocess.run`, recording the command it was given."""

    def __init__(
        self,
        stdout: str = "",
        returncode: int = 0,
        error: Exception | None = None,
        write_path: Path | None = None,
    ):
        self.stdout = stdout
        self.returncode = returncode
        self.error = error
        self.write_path = write_path
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_: Any) -> Any:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        if self.write_path is not None:
            output = Path(command[command.index("--out") + 1])
            written = output / GRAPHIFY_OUT / GRAPH_FILE
            written.parent.mkdir(parents=True, exist_ok=True)
            written.write_text('{"nodes": [], "links": []}', encoding="utf-8")
        return subprocess.CompletedProcess(command, self.returncode, self.stdout, "boom")


@pytest.fixture
def graphify(monkeypatch: pytest.MonkeyPatch):
    """Pretend Graphify's CLI is installed, and capture what it is asked."""

    def install(run: FakeRun) -> FakeRun:
        monkeypatch.setattr(
            "skillgen.graph.connections.find_graphify_command", lambda: "/bin/graphify"
        )
        monkeypatch.setattr("skillgen.graph.connections.subprocess.run", run)
        return run

    return install


def test_explain_node_asks_graphify_and_keeps_its_answer(graphify):
    run = graphify(FakeRun(stdout=EXPLAIN))
    lines = explain_node(GraphifyGraph(path=Path("g.json")), "ClaimForm.vue")
    assert run.commands[0][1:] == ["explain", "ClaimForm.vue", "--graph", "g.json"]
    assert lines[0] == "Node: ClaimForm.vue"
    # Its own blank lines are dropped; the connections, with relations, are kept.
    assert "" not in lines
    assert any("CollapsiblePanel.vue [imports_from]" in line for line in lines)


def test_find_path_asks_graphify_for_the_route_between_two_parts(graphify):
    run = graphify(FakeRun(stdout="Shortest path (2 hops):\n  A --imports_from--> B\n"))
    lines = find_path(GraphifyGraph(path=Path("g.json")), "ClaimForm", "Modal")
    assert run.commands[0][1:] == ["path", "ClaimForm", "Modal", "--graph", "g.json"]
    assert lines == ["Shortest path (2 hops):", "  A --imports_from--> B"]


def test_explain_caches_only_successful_answers_by_graph_fingerprint(graphify, tmp_path):
    run = graphify(FakeRun(stdout=EXPLAIN))
    graph = GraphifyGraph(
        path=Path("g.json"), fingerprint="source-a", answer_cache=tmp_path / "explain"
    )
    expected = explain_node(graph, "ClaimForm.vue")
    assert explain_node(graph, "ClaimForm.vue") == expected
    assert len(run.commands) == 1
    assert list((tmp_path / "explain").glob("*.json"))

    changed = GraphifyGraph(
        path=Path("g.json"), fingerprint="source-b", answer_cache=tmp_path / "explain"
    )
    explain_node(changed, "ClaimForm.vue")
    assert len(run.commands) == 2


def test_explain_does_not_cache_failures_or_use_corrupt_cache(graphify, tmp_path):
    run = graphify(FakeRun(returncode=2))
    graph = GraphifyGraph(
        path=Path("g.json"), fingerprint="source-a", answer_cache=tmp_path / "explain"
    )
    assert explain_node(graph, "ClaimForm.vue") == []
    assert not (tmp_path / "explain").exists()

    cache = tmp_path / "explain"
    cache.mkdir()
    (cache / "broken.json").write_text("not json", encoding="utf-8")
    graph = GraphifyGraph(path=Path("g.json"), fingerprint="source-a", answer_cache=cache)
    assert explain_node(graph, "ClaimForm.vue") == []
    assert len(run.commands) == 2


def test_an_answer_is_bounded_so_a_hub_cannot_fill_a_prompt(graphify):
    graphify(FakeRun(stdout="\n".join(f"line {n}" for n in range(200))))
    assert len(explain_node(GraphifyGraph(path=Path("g.json")), "hub")) == MAX_ANSWER_LINES


@pytest.mark.parametrize(
    "answer", ["", "   \n", "No node matching 'x' found.", "error: graph file not found"]
)
def test_nothing_is_reported_when_graphify_has_no_answer(graphify, answer):
    graphify(FakeRun(stdout=answer))
    assert explain_node(GraphifyGraph(path=Path("g.json")), "x") == []


def test_a_failing_command_is_survived_rather_than_raised(graphify):
    graphify(FakeRun(stdout="", returncode=2))
    assert explain_node(GraphifyGraph(path=Path("g.json")), "x") == []


@pytest.mark.parametrize(
    "error", [OSError("not executable"), subprocess.TimeoutExpired("graphify", 60)]
)
def test_a_crash_or_a_timeout_is_survived(graphify, error):
    graphify(FakeRun(error=error))
    assert find_path(GraphifyGraph(path=Path("g.json")), "a", "b") == []


def test_nothing_is_asked_when_graphifys_cli_is_not_installed(monkeypatch):
    monkeypatch.setattr("skillgen.graph.connections.find_graphify_command", lambda: "")

    def fail(*_: Any, **__: Any) -> Any:
        raise AssertionError("no command should run without graphify")

    monkeypatch.setattr("skillgen.graph.connections.subprocess.run", fail)
    assert explain_node(GraphifyGraph(path=Path("g.json")), "x") == []


def test_build_graph_asks_for_an_ast_only_build_and_finds_what_it_wrote(graphify, tmp_path):
    """`--code-only` keeps it to the AST pass, so no model is called for a build."""
    written = tmp_path / GRAPHIFY_OUT / GRAPH_FILE
    run = graphify(FakeRun(stdout="wrote graph", write_path=written))
    built = build_graph(Path("/repo"), tmp_path)
    assert built is not None and built.path == written
    asked = run.commands[0][1:]
    assert asked[0] == "extract"
    for flag in ("--code-only", "--no-cluster"):
        assert flag in asked


def test_successful_build_publishes_a_fingerprint_receipt(graphify, tmp_path):
    written = tmp_path / GRAPHIFY_OUT / GRAPH_FILE
    graphify(FakeRun(stdout="wrote graph", write_path=written))
    built = build_graph(Path("/repo"), tmp_path, fingerprint="source-a")
    assert built is not None
    assert load_graph_metadata(written) is not None
    assert load_graph_metadata(written) == ("source-a", built.tool_version)


def test_build_graph_reports_nothing_when_graphify_wrote_no_graph(graphify, tmp_path):
    graphify(FakeRun(stdout="nothing useful"))
    assert build_graph(Path("/repo"), tmp_path) is None


def test_failed_rebuild_does_not_return_an_old_query_graph(graphify, tmp_path):
    graphify(FakeRun(returncode=1))
    written = tmp_path / GRAPHIFY_OUT / GRAPH_FILE
    written.parent.mkdir(parents=True)
    written.write_text("old", encoding="utf-8")
    assert build_graph(Path("/repo"), tmp_path) is None
    assert written.read_text(encoding="utf-8") == "old"


def test_successful_rebuild_without_a_graph_does_not_return_old_output(graphify, tmp_path):
    graphify(FakeRun(stdout="nothing useful"))
    written = tmp_path / GRAPHIFY_OUT / GRAPH_FILE
    written.parent.mkdir(parents=True)
    written.write_text("old", encoding="utf-8")
    assert build_graph(Path("/repo"), tmp_path) is None
    assert written.read_text(encoding="utf-8") == "old"


def test_find_graphify_command_returns_a_path_or_nothing():
    found = find_graphify_command()
    assert found == "" or Path(found).name.startswith("graphify")
