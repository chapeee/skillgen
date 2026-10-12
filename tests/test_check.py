import subprocess

import pytest

from skillgen.config import Settings
from skillgen.drift.check import find_drift, list_changed_files, read_slices
from skillgen.errors import WorkspaceError
from skillgen.graph.codegraph import CodeGraph
from skillgen.model.route import RouteEntry, RouteTable
from skillgen.workspace import Workspace, write_json


def git(root, *arguments):
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
    )


def make_workspace(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create(Settings())
    workspace.write_routes(
        RouteTable(
            (
                RouteEntry("/a", "x-a", has_form=True),
                RouteEntry("/b", "x-b", has_form=True),
                RouteEntry("/c", "x-c", has_form=False),
            )
        )
    )
    write_json(
        workspace.page_folder("x-a") / "slice.json", {"files": [["a.tsx", 0], ["shared.ts", 1]]}
    )
    return workspace


def test_list_changed_files_includes_untracked(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("1")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "one")
    (tmp_path / "a.txt").write_text("2")
    (tmp_path / "new.txt").write_text("n")
    assert list_changed_files(tmp_path, "HEAD") == ["a.txt", "new.txt"]


def test_list_changed_files_reports_git_errors(tmp_path):
    with pytest.raises(WorkspaceError, match="git failed"):
        list_changed_files(tmp_path, "HEAD")


def test_read_slices_reads_saved_slices(tmp_path):
    assert read_slices(make_workspace(tmp_path), ["x-a", "x-b"]) == {"x-a": ["a.tsx", "shared.ts"]}


def test_find_drift_uses_impact_through_graph(tmp_path):
    workspace = make_workspace(tmp_path)
    graph = CodeGraph(files=("shared.ts", "util.ts"), edges=(("shared.ts", "util.ts", "imports"),))
    report = find_drift(workspace, graph, ["util.ts"])
    assert report.stale_skills == ("x-a",)
    assert report.unknown_skills == ("x-b",)


def test_find_drift_without_graph_matches_slices(tmp_path):
    workspace = make_workspace(tmp_path)
    assert find_drift(workspace, None, ["util.ts"]).stale_skills == ()
    assert find_drift(workspace, None, ["a.tsx"]).stale_skills == ("x-a",)
