import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from skillgen.analyze.prompt import AnalysisRequest
from skillgen.config import Settings
from skillgen.errors import AnalysisError
from skillgen.graph.codegraph import CodeGraph
from skillgen.graph.connections import GraphifyGraph
from skillgen.model.page import Box, Layout
from skillgen.model.probe import ProbedPage
from skillgen.model.route import Question, RouteCandidate, RouteEntry, RouteTable
from skillgen.pipeline import (
    ask_claude_for_routes,
    build_slice,
    choose_prefix,
    describe_page_connections,
    ensure_route,
    find_reusable_analysis,
    fingerprint_request,
    keep_proven_views,
    merge_questions,
    next_version,
    refresh_entry_files,
    restore_skill_names,
    summarize_probe,
)
from skillgen.workspace import Workspace
from tests.conftest import FIXTURES
from tests.helpers import load_bench_page, load_wizard_page

SIGNUP = FIXTURES / "react-router-spa" / "analyses" / "signup.json"


def test_choose_prefix_order():
    root = Path("/repo/My App")
    assert choose_prefix(Settings(app_name="Acme"), root, "Shop") == "shop"
    assert choose_prefix(Settings(app_name="Acme", name_prefix="ac"), root) == "ac"
    assert choose_prefix(Settings(app_name="Acme Admin"), root) == "acme-admin"
    assert choose_prefix(Settings(), root) == "my-app"


def test_merge_questions_keeps_answers_and_other_skills():
    old = [
        Question("q1", "a", "rule:1", "?", answer="yes"),
        Question("q2", "b", "x", "?"),
        Question("q3", "a", "gone", "?", answer="no"),
    ]
    new = [Question("q1", "a", "rule:1", "?"), Question("q4", "a", "field:x:required", "?")]
    merged = merge_questions(old, "a", new)
    by_id = {q.id: q.answer for q in merged}
    assert by_id == {"q2": "", "q3": "no", "q1": "yes", "q4": ""}


def test_next_version_bumps_only_on_change():
    page = load_bench_page()
    assert next_version(None, page) == 1
    assert next_version(page, replace(page, source_commit="abc")) == page.version
    assert next_version(page, replace(page, title="Other")) == page.version + 1


def test_build_slice_without_graph_uses_entry_files(tmp_path):
    (tmp_path / "a.tsx").write_text("x")
    entry = RouteEntry("/a", "x-a", entry_files=("a.tsx", "missing.tsx"))
    page_slice = build_slice(Workspace(tmp_path), Settings(), entry, None)
    assert page_slice.paths == ("a.tsx",)


def test_describe_page_connections_uses_the_shared_graph_without_rebuilding(tmp_path, monkeypatch):
    """Route analysis reads one graph supplied by the run rather than extracting again."""
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    graph = CodeGraph(files=("Form.tsx",), edges=())
    query_graph = GraphifyGraph(path=tmp_path / "graph.json")
    seen = []

    def explain(built, label):
        seen.append((built, label))
        return ["Node: Form.tsx"]

    def fail(*_):
        raise AssertionError("the shared graph should avoid another extract")

    monkeypatch.setattr("skillgen.pipeline.explain_node", explain)
    monkeypatch.setattr("skillgen.pipeline.load_graphify_graph", fail)
    lines = describe_page_connections(workspace, graph, ("Form.tsx",), query_graph)

    assert lines == ("Node: Form.tsx",)
    assert seen == [(query_graph, "Form.tsx")]


def test_summarize_probe_has_no_evidence():
    summary = summarize_probe(ProbedPage(url="http://x", title="t", fields=()))
    assert set(summary) == {"title", "fields", "clickable", "submit"}


def test_summarize_probe_offers_only_the_clickables_worth_naming():
    """The page's own menus, links away from it and costly controls are left out."""
    worth = {
        "label": "Witnesses",
        "step": "#w",
        "role": "summary",
        "visible": True,
        "collapsed": True,
    }
    page = ProbedPage(
        url="http://x",
        title="t",
        fields=(),
        clickables=(
            worth,
            {"label": "Menu", "step": "#m", "visible": True, "chrome": True},
            {"label": "Away", "step": "#a", "visible": True, "leaves": True},
            {"label": "Submit", "step": "#s", "visible": True, "risky": True},
            {"label": "Later", "step": "#l", "visible": False},
        ),
    )
    offered = summarize_probe(page)["clickable"]
    assert offered == [
        {"label": "Witnesses", "role": "summary", "click": "#w", "opens_something": True}
    ]


def test_ask_claude_for_routes_keeps_existing_files_only(tmp_path, monkeypatch):
    (tmp_path / "views").mkdir()
    (tmp_path / "views" / "signup.html").write_text("<form></form>")
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    seen = {}

    def fake(repository, prompt):
        seen["prompt"] = prompt
        return [
            {
                "route": "/signup",
                "entry_files": ["views/signup.html", "ghost.py"],
                "title": "Sign up",
            }
        ]

    monkeypatch.setattr("skillgen.pipeline.list_routes_with_claude", fake)
    graph = CodeGraph(
        files=("main.py", "views/signup.html"),
        edges=(("main.py", "views/signup.html", "references"),),
    )
    (candidate,) = ask_claude_for_routes(workspace, Settings(app_name="Shop"), graph, ["/home"])
    assert candidate.entry_files == ("views/signup.html",) and candidate.source == "claude"
    assert "- main.py" in seen["prompt"] and "- /home" in seen["prompt"]
    assert (workspace.folder / "route-listing-prompt.md").exists()


PATTERN = RouteCandidate("/users/:id", "folder", ("app/users/[id]/page.tsx",))
# Any graph will do: ensure_route only uses its presence to decide whether discovery
# could resolve a route's component, which is what makes saved files replaceable.
GRAPH = CodeGraph(files=("router.tsx", "app/users/[id]/page.tsx"), edges=())


def test_ensure_route_links_a_new_concrete_page_to_its_pattern(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    monkeypatch.setattr("skillgen.pipeline.find_route_candidates", lambda *_: [PATTERN])
    entry = ensure_route(workspace, Settings(app_name="Shop"), "/users/7")
    assert entry.route == "/users/7"
    assert entry.entry_files == ("app/users/[id]/page.tsx",)


def test_ensure_route_reuses_candidates_already_found_for_the_run(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))

    def fail(*_):
        raise AssertionError("route sources should only run once per generate run")

    monkeypatch.setattr("skillgen.pipeline.find_route_candidates", fail)
    entry = ensure_route(
        workspace,
        Settings(app_name="Shop"),
        "/users/7",
        route_candidates=(PATTERN,),
    )
    assert entry.entry_files == ("app/users/[id]/page.tsx",)


def test_ensure_route_fills_code_files_of_a_saved_route(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    saved = RouteEntry(route="/users/7", skill="shop-user", sources=("user",))
    workspace.write_routes(RouteTable(entries=(saved,)))
    monkeypatch.setattr("skillgen.pipeline.find_route_candidates", lambda *_: [PATTERN])
    entry = ensure_route(workspace, Settings(app_name="Shop"), "shop-user")
    assert entry.skill == "shop-user"
    assert entry.entry_files == ("app/users/[id]/page.tsx",)
    saved_again = workspace.read_routes().find("/users/7")
    assert saved_again is not None and saved_again.entry_files == entry.entry_files


def test_ensure_route_keeps_a_saved_route_with_code_files(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    saved = RouteEntry(route="/users/7", skill="shop-user", entry_files=("mine.tsx",))
    workspace.write_routes(RouteTable(entries=(saved,)))

    def fail(*_):
        raise AssertionError("no lookup needed")

    monkeypatch.setattr("skillgen.pipeline.find_route_candidates", fail)
    assert ensure_route(workspace, Settings(), "/users/7").entry_files == ("mine.tsx",)


def test_ensure_route_replaces_a_router_entry_once_the_graph_resolves_the_page(
    tmp_path, monkeypatch
):
    """A route saved before its component could be resolved must not stay wrong.

    Without a graph the only entry on offer is the router that declares every route,
    and slicing from it pulls in every other page.
    """
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    saved = RouteEntry(route="/users/7", skill="shop-user", entry_files=("router.tsx",))
    workspace.write_routes(RouteTable(entries=(saved,)))
    resolved = RouteCandidate("/users/7", "router:x", ("app/users/[id]/page.tsx",))
    monkeypatch.setattr("skillgen.pipeline.find_route_candidates", lambda *_: [resolved])
    entry = ensure_route(workspace, Settings(app_name="Shop"), "/users/7", GRAPH)
    assert entry.entry_files == ("app/users/[id]/page.tsx",)
    assert entry.skill == "shop-user"
    again = workspace.read_routes().find("/users/7")
    assert again is not None and again.entry_files == entry.entry_files


def test_ensure_route_without_a_graph_leaves_saved_code_files_alone(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    saved = RouteEntry(route="/users/7", skill="shop-user", entry_files=("mine.tsx",))
    workspace.write_routes(RouteTable(entries=(saved,)))
    monkeypatch.setattr("skillgen.pipeline.find_route_candidates", lambda *_: [PATTERN])
    assert ensure_route(workspace, Settings(), "/users/7").entry_files == ("mine.tsx",)


def test_refresh_entry_files_corrects_every_route_of_a_whole_run(tmp_path, monkeypatch):
    """`generate --all` reads the saved table, so it needs its own refresh.

    Without this a route saved before its component could be resolved keeps slicing
    the router that declares every route, and so the whole app.
    """
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    stale = RouteEntry(route="/users/7", skill="shop-user", entry_files=("router.tsx",))
    other = RouteEntry(route="/about", skill="shop-about", entry_files=("about.tsx",))
    workspace.write_routes(RouteTable(entries=(stale, other)))
    resolved = RouteCandidate("/users/7", "router:x", ("app/users/[id]/page.tsx",))
    monkeypatch.setattr("skillgen.pipeline.find_route_candidates", lambda *_: [resolved])
    entries = refresh_entry_files(workspace, Settings(), [stale, other], GRAPH)
    assert [entry.entry_files for entry in entries] == [
        ("app/users/[id]/page.tsx",),
        ("about.tsx",),
    ]
    saved = workspace.read_routes()
    assert (saved.find("/users/7") or stale).entry_files == ("app/users/[id]/page.tsx",)
    # A route the code no longer declares keeps what it has; dropping routes is `routes`.
    assert (saved.find("/about") or other).entry_files == ("about.tsx",)


def test_refresh_entry_files_without_a_graph_touches_nothing(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    stale = RouteEntry(route="/users/7", skill="shop-user", entry_files=("router.tsx",))
    workspace.write_routes(RouteTable(entries=(stale,)))

    def fail(*_):
        raise AssertionError("no lookup without a graph")

    monkeypatch.setattr("skillgen.pipeline.find_route_candidates", fail)
    assert refresh_entry_files(workspace, Settings(), [stale], None) == [stale]


def test_restore_skill_names_reverts_a_rename_but_keeps_discovered_files(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    before = RouteEntry(route="/users/7", skill="shop-user", entry_files=("router.tsx",))
    workspace.write_routes(RouteTable(entries=(before,)))
    routes_before = workspace.routes_path.read_text(encoding="utf-8")
    renamed = replace(before, skill="my-name", entry_files=("app/users/[id]/page.tsx",))
    workspace.write_routes(RouteTable(entries=(renamed,)))
    restore_skill_names(workspace, routes_before)
    entry = workspace.read_routes().find("/users/7")
    assert entry is not None
    assert entry.skill == "shop-user"
    assert entry.entry_files == ("app/users/[id]/page.tsx",)


def make_request(tmp_path):
    (tmp_path / "Form.tsx").write_text("export const a = 1;")
    workspace = Workspace(tmp_path)
    request = AnalysisRequest(
        route="/a", skill="shop-a", app_name="Shop", slice_files=("Form.tsx",)
    )
    return workspace, request


def test_fingerprint_request_changes_when_a_slice_file_changes(tmp_path):
    workspace, request = make_request(tmp_path)
    before = fingerprint_request(workspace, request)
    assert fingerprint_request(workspace, request) == before
    (tmp_path / "Form.tsx").write_text("export const a = 2;")
    assert fingerprint_request(workspace, request) != before


def test_fingerprint_request_distinguishes_missing_and_empty_slice_files(tmp_path):
    workspace, request = make_request(tmp_path)
    request = replace(request, slice_files=("Missing.tsx",))
    missing = fingerprint_request(workspace, request)
    (tmp_path / "Missing.tsx").write_text("")
    assert fingerprint_request(workspace, request) != missing


def write_analysis(folder):
    analysis = json.loads(SIGNUP.read_text("utf-8"))
    (folder / "analysis.json").write_text(json.dumps(analysis), "utf-8")
    return analysis


def test_find_reusable_analysis_uses_one_made_from_the_same_code(tmp_path):
    analysis = write_analysis(tmp_path)
    (tmp_path / "analysis.fingerprint").write_text("abc")
    assert find_reusable_analysis(tmp_path, "abc") == analysis
    assert find_reusable_analysis(tmp_path, "changed") is None


def test_find_reusable_analysis_takes_the_answer_to_the_last_request(tmp_path):
    request = tmp_path / "request.fingerprint"
    request.write_text("abc")
    os.utime(request, (1_000_000, 1_000_000))
    analysis = write_analysis(tmp_path)
    assert find_reusable_analysis(tmp_path, "abc") == analysis
    assert (tmp_path / "analysis.fingerprint").read_text() == "abc"


def test_find_reusable_analysis_ignores_one_older_than_the_request(tmp_path):
    write_analysis(tmp_path)
    os.utime(tmp_path / "analysis.json", (1_000_000, 1_000_000))
    (tmp_path / "request.fingerprint").write_text("abc")
    assert find_reusable_analysis(tmp_path, "abc") is None


def test_find_reusable_analysis_reports_an_answer_off_the_schema(tmp_path):
    request = tmp_path / "request.fingerprint"
    request.write_text("abc")
    os.utime(request, (1_000_000, 1_000_000))
    (tmp_path / "analysis.json").write_text('{"fields": "nope"}')
    with pytest.raises(AnalysisError):
        find_reusable_analysis(tmp_path, "abc")


def test_find_reusable_analysis_takes_an_unrecorded_one_newer_than_its_code(tmp_path):
    analysis = write_analysis(tmp_path)
    assert find_reusable_analysis(tmp_path, "abc", newest_source=1_000_000) == analysis
    assert (tmp_path / "analysis.fingerprint").read_text() == "abc"


def test_find_reusable_analysis_skips_an_unrecorded_one_older_than_its_code(tmp_path):
    write_analysis(tmp_path)
    assert find_reusable_analysis(tmp_path, "abc", newest_source=9_999_999_999) is None


def test_fingerprint_request_changes_when_prompt_context_changes(tmp_path):
    workspace, request = make_request(tmp_path)
    before = fingerprint_request(workspace, request)
    changed = (
        replace(request, route="/b"),
        replace(request, skill="other"),
        replace(request, app_name="Other"),
        replace(request, is_slice_truncated=True),
        replace(request, probe_summary={"title": "Live"}),
        replace(request, hint_facts=("a validator fact",)),
        replace(request, connection_lines=("Form imports Validator",)),
    )
    assert all(fingerprint_request(workspace, item) != before for item in changed)


def test_fingerprint_request_includes_prompt_and_schema_identity(tmp_path, monkeypatch):
    workspace, request = make_request(tmp_path)
    before = fingerprint_request(workspace, request)
    monkeypatch.setattr("skillgen.pipeline.PROMPT_VERSION", 99)
    assert fingerprint_request(workspace, request) != before
    monkeypatch.setattr("skillgen.pipeline.PROMPT_VERSION", 3)
    monkeypatch.setattr("skillgen.pipeline.schema_for_claude", lambda name: {"title": "changed"})
    assert fingerprint_request(workspace, request) != before


def test_find_reusable_analysis_treats_an_old_style_record_as_unrecorded(tmp_path):
    analysis = write_analysis(tmp_path)
    (tmp_path / "analysis.fingerprint").write_text("0123abcd")
    current = "analysis-v2:new"
    assert find_reusable_analysis(tmp_path, current, newest_source=1_000_000) == analysis
    assert (tmp_path / "analysis.fingerprint").read_text() == current


def test_find_reusable_analysis_does_not_adopt_a_code_only_record(tmp_path):
    write_analysis(tmp_path)
    (tmp_path / "analysis.fingerprint").write_text("code-v1:old")
    assert find_reusable_analysis(tmp_path, "analysis-v2:new", newest_source=1_000_000) is None


def test_keep_proven_views_keeps_views_whose_fields_appeared_in_order():
    walked = load_wizard_page()
    trusted = replace(walked, views=())
    seen = Layout(1280, 900, (("first_name", Box(0, 0, 10, 10)), ("city", Box(0, 40, 10, 10))))
    page, has_all = keep_proven_views(trusted, walked, seen)
    assert [view.name for view in page.views] == ["Address tab"] and not has_all
    every = Layout(1280, 900, tuple((spec.key, Box(0, 0, 10, 10)) for spec in walked.fields))
    page, has_all = keep_proven_views(trusted, walked, every)
    assert len(page.views) == 4 and has_all
