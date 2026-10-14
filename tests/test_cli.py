import importlib.util
import io
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import skillgen.cli as skillgen_cli
import skillgen.probe.runner as probe_runner
from skillgen import TOOL_NAME
from skillgen.analyze.runner import ClaudeCodeAnalyzer
from skillgen.cli import (
    EXIT_NEEDS,
    HANDLERS,
    build_parser,
    describe_export_use,
    main,
    use_utf8_output,
)
from skillgen.config import Settings
from skillgen.errors import ActionNeededError, AnalysisError, Need
from skillgen.graph.codegraph import CodeGraph
from skillgen.graph.connections import GraphifyGraph
from skillgen.model.page import Box, Layout
from skillgen.model.route import RouteCandidate, RouteEntry, RouteTable
from skillgen.schema import find_schema_problems, list_cli_schemas
from skillgen.workspace import Workspace
from tests.conftest import FIXTURES


def run(capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, dict]:  # type: ignore[type-arg]
    code = main([*arguments, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_every_command_has_an_output_schema():
    assert set(HANDLERS) <= set(list_cli_schemas())


def test_use_utf8_output_encodes_marks_on_ansi_pipe(monkeypatch):
    piped = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", piped)
    use_utf8_output()
    piped.write("✓ done")
    piped.flush()
    assert piped.buffer.getvalue().decode("utf-8") == "✓ done"


def test_every_command_accepts_json_flag():
    parser = build_parser()
    for command in HANDLERS:
        required = {
            "answer": ["q", "a"],
            "add-rule": ["rule"],
            "prepare": ["--route", "/x"],
            "generate": ["--all"],
            "generate-url": ["https://example.com/form", "--name", "example-form"],
            "probe": ["--route", "/x"],
        }
        assert parser.parse_args([command, *required.get(command, []), "--json"]).json


def test_doctor_reports_checks(capsys):
    code, data = run(capsys, "doctor")
    assert {check["name"] for check in data["checks"]} >= {"python", "graphify", "claude"}
    assert code in (0, 1)
    assert find_schema_problems(data, "cli/doctor") == []


def test_init_then_questions(tmp_path, capsys):
    code, data = run(
        capsys,
        "init",
        "--root",
        str(tmp_path),
        "--app-name",
        "Acme",
        "--url",
        "http://localhost:3000",
    )
    assert code == 0 and data["is_new"] and data["app_url"] == "http://localhost:3000"
    code, data = run(capsys, "questions", "--root", str(tmp_path))
    assert data == {"ok": True, "command": "questions", "questions": [], "open": 0}


def test_init_rejects_bad_url(tmp_path, capsys):
    code, data = run(capsys, "init", "--root", str(tmp_path), "--url", "localhost")
    assert code == 2 and not data["ok"] and "http://" in data["error"]


def test_commands_need_a_workspace(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, data = run(capsys, "routes")
    assert code == 2 and "init" in data["error"]


def test_install_writes_command_agent_and_skill(tmp_path, capsys):
    code, data = run(capsys, "install", "--target", str(tmp_path), "--no-chromium")
    assert code == 0 and len(data["installed"]) == 3
    assert data["chromium"] == "chromium skipped (--no-chromium)"
    command = (tmp_path / "commands" / f"{TOOL_NAME}.md").read_text(encoding="utf-8")
    assert "{{tool}}" not in command and f"{TOOL_NAME} routes" in command
    skill = (tmp_path / "skills" / TOOL_NAME / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith(f"---\nname: {TOOL_NAME}\n")


def test_prepare_writes_prompt_for_claude_code(tmp_path, capsys):
    run(capsys, "init", "--root", str(tmp_path))
    code, data = run(
        capsys,
        "prepare",
        "--route",
        "/signup",
        "--root",
        str(tmp_path),
        "--no-graph",
        "--name",
        "join",
    )
    assert code == 0 and data["skill"] == "join"
    # Paths are native: compare them as paths, not as "/"-separated text.
    assert Path(data["analysis_path"]).parts[-2:] == ("join", "analysis.json")
    assert "page-analysis" in data["prompt"]


def test_validate_and_add_rule_on_generated_skill(tmp_path, capsys):
    root = tmp_path
    (root / "src").mkdir()
    run(capsys, "init", "--root", str(root), "--app-name", "Shop")
    replay = str(FIXTURES / "react-router-spa" / "analyses")
    run(
        capsys,
        "generate",
        "--route",
        "/signup",
        "--root",
        str(root),
        "--analyzer",
        "replay",
        "--replay-dir",
        replay,
        "--no-graph",
    )
    code, data = run(capsys, "validate", "--root", str(root))
    assert code == 0 and data["results"] == [
        {"skill": "shop-signup", "ok": True, "problems": [], "notes": []}
    ]
    code, data = run(
        capsys, "add-rule", "shop-signup", "Plan must be chosen by the user.", "--root", str(root)
    )
    assert code == 0
    code, data = run(capsys, "add-rule", "Use British spelling.", "--global", "--root", str(root))
    assert code == 0 and data["global"]
    code, data = run(capsys, "add-rule", "nope", "x", "--check", "a ([", "--root", str(root))
    assert code == 2


def test_validate_reports_problems(tmp_path, capsys):
    run(capsys, "init", "--root", str(tmp_path))
    folder = tmp_path / "skills" / "broken"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("no frontmatter")
    code, data = run(capsys, "validate", "--root", str(tmp_path))
    assert code == 1 and not data["results"][0]["ok"]


def test_answer_unknown_question(tmp_path, capsys):
    run(capsys, "init", "--root", str(tmp_path))
    code, data = run(capsys, "answer", "q000000", "yes", "--root", str(tmp_path))
    assert code == 2 and "no question" in data["error"]


def test_text_output_without_json(tmp_path, capsys):
    assert main(["init", "--root", str(tmp_path), "--app-name", "Acme"]) == 0
    assert "Created" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["generate"])
def test_generate_requires_route_or_all(command):
    with pytest.raises(SystemExit):
        build_parser().parse_args([command])


def test_index_check_and_export_commands(tmp_path, capsys):
    root = tmp_path
    (root / "package.json").write_text("{}")
    (root / "app" / "contact").mkdir(parents=True)
    (root / "app" / "contact" / "page.tsx").write_text(
        "export default function C() { return null; }"
    )
    run(capsys, "init", "--root", str(root), "--app-name", "Store")
    replay = str(FIXTURES / "nextjs-app" / "analyses")
    run(
        capsys,
        "generate",
        "--route",
        "/contact",
        "--root",
        str(root),
        "--analyzer",
        "replay",
        "--replay-dir",
        replay,
    )
    code, data = run(capsys, "index", "--root", str(root))
    assert code == 0 and data["skills"] == 1 and (root / "skills-index.html").exists()
    code, data = run(capsys, "export", "--zip", "--plugin", "--root", str(root))
    assert code == 0 and data["path"].endswith("store.zip") and data["plugin"] == "store"
    code, data = run(capsys, "export", "--one-skill", "--zip", "--root", str(root))
    assert code == 0 and data["skill"] == "store" and not data["plugin"]
    assert Path(data["path"]) == (root / "dist" / "skill" / "store.zip").resolve()
    code, data = run(capsys, "export-chatgpt", "--zip", "--root", str(root))
    assert code == 0 and data["plugin"] == "store" and data["skills"] == ["store-contact"]
    assert Path(data["path"]) == (root / "dist" / "chatgpt" / "store.zip").resolve()
    for command in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "x"],
    ):
        subprocess.run(["git", *command], cwd=root, check=True, capture_output=True)
    (root / "app" / "contact" / "page.tsx").write_text("export default function C() { return 1; }")
    code, data = run(capsys, "check", "--since", "HEAD", "--root", str(root))
    assert data["changed_files"] == ["app/contact/page.tsx"]
    assert data["stale"] == ["store-contact"] and code == 1


def test_probe_needs_a_url(tmp_path, capsys):
    run(capsys, "init", "--root", str(tmp_path))
    code, data = run(capsys, "probe", "--route", "/x", "--root", str(tmp_path))
    assert code == 2 and "dev URL" in data["error"]


def test_routes_asks_claude_only_when_nothing_is_found(tmp_path, capsys, monkeypatch):
    calls = []

    def fake(workspace, settings, graph, known):
        calls.append(list(known))
        return [RouteCandidate("/signup", "claude")]

    monkeypatch.setattr("skillgen.cli.ask_claude_for_routes", fake)
    run(capsys, "init", "--root", str(tmp_path))
    _, data = run(capsys, "routes", "--all", "--no-graph", "--no-claude", "--root", str(tmp_path))
    assert data["count"] == 0 and calls == []
    _, data = run(capsys, "routes", "--all", "--no-graph", "--root", str(tmp_path))
    assert [r["route"] for r in data["routes"]] == ["/signup"] and calls == [[]]
    run(capsys, "routes", "--all", "--no-graph", "--root", str(tmp_path))
    assert len(calls) == 1
    run(capsys, "routes", "--all", "--no-graph", "--ask-claude", "--root", str(tmp_path))
    assert calls[-1] == ["/signup"]


def make_shop(root, capsys):
    (root / "src").mkdir()
    run(capsys, "init", "--root", str(root), "--app-name", "Shop")
    return root


def generate_signup(capsys, root, *extra, replay=None):
    folder = replay or str(FIXTURES / "react-router-spa" / "analyses")
    return run(
        capsys,
        "generate",
        "--route",
        "/signup",
        "--root",
        str(root),
        "--analyzer",
        "replay",
        "--replay-dir",
        folder,
        "--no-graph",
        *extra,
    )


def test_generate_builds_one_shared_query_graph_for_all_routes(tmp_path, capsys, monkeypatch):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    for name in ("one.ts", "two.ts"):
        (tmp_path / name).write_text("export const value = 1;", encoding="utf-8")
    workspace.write_routes(
        RouteTable(
            entries=(
                RouteEntry("/one", "shop-one", entry_files=("one.ts",)),
                RouteEntry("/two", "shop-two", entry_files=("two.ts",)),
            )
        )
    )
    graph = CodeGraph(files=("one.ts", "two.ts"), edges=())
    query_graph = GraphifyGraph(path=tmp_path / "graph.json")
    builds = []
    seen = []

    monkeypatch.setattr(skillgen_cli, "try_load_graph", lambda _: graph)

    def load_query_graph(_, loaded):
        builds.append(loaded)
        return query_graph

    monkeypatch.setattr(skillgen_cli, "try_load_graphify_graph", load_query_graph)
    monkeypatch.setattr(
        skillgen_cli,
        "refresh_entry_files",
        lambda _, __, entries, ___, **_kwargs: list(entries),
    )

    def fake_analyze(_, __, entry, options):
        seen.append((entry.route, options.graphify_graph))
        return {"has_form": False, "fields": []}

    monkeypatch.setattr(skillgen_cli, "analyze_route", fake_analyze)
    code, data = run(
        capsys,
        "generate",
        "--all",
        "--root",
        str(tmp_path),
        "--analyzer",
        "replay",
        "--replay-dir",
        str(FIXTURES / "react-router-spa" / "analyses"),
    )

    assert code == 0 and data["written"] == 0
    assert builds == [graph]
    assert {route for route, _ in seen} == {"/one", "/two"}
    assert all(shared is query_graph for _, shared in seen)


def test_generate_does_not_retry_a_failed_query_graph_for_each_route(tmp_path, capsys, monkeypatch):
    workspace = Workspace(tmp_path)
    workspace.create(Settings(app_name="Shop"))
    for name in ("one.ts", "two.ts"):
        (tmp_path / name).write_text("export const value = 1;", encoding="utf-8")
    workspace.write_routes(
        RouteTable(
            entries=(
                RouteEntry("/one", "shop-one", entry_files=("one.ts",)),
                RouteEntry("/two", "shop-two", entry_files=("two.ts",)),
            )
        )
    )
    graph = CodeGraph(files=("one.ts", "two.ts"), edges=())
    attempts = []
    load_options = []

    monkeypatch.setattr(skillgen_cli, "try_load_graph", lambda _: graph)

    def fail_query_graph(_, loaded):
        attempts.append(loaded)
        return

    monkeypatch.setattr(skillgen_cli, "try_load_graphify_graph", fail_query_graph)
    monkeypatch.setattr(
        skillgen_cli,
        "refresh_entry_files",
        lambda _, __, entries, ___, **_kwargs: list(entries),
    )

    def fake_analyze(_, __, entry, options):
        load_options.append((entry.route, options.graphify_graph, options.should_load_graphify))
        return {"has_form": False, "fields": []}

    monkeypatch.setattr(skillgen_cli, "analyze_route", fake_analyze)
    code, data = run(
        capsys,
        "generate",
        "--all",
        "--root",
        str(tmp_path),
        "--analyzer",
        "replay",
        "--replay-dir",
        str(FIXTURES / "react-router-spa" / "analyses"),
    )

    assert code == 0 and data["written"] == 0
    assert attempts == [graph]
    assert all(graph is None and not should_load for _, graph, should_load in load_options)


def test_generate_all_scans_for_route_candidates_once_when_none_match(
    tmp_path, capsys, monkeypatch
):
    calls = []

    def find_candidates(workspace, settings, graph):
        calls.append((workspace.root, settings, graph))
        return []

    monkeypatch.setattr(skillgen_cli, "find_route_candidates", find_candidates)
    run(capsys, "init", "--root", str(tmp_path))
    code, data = run(
        capsys,
        "generate",
        "--all",
        "--root",
        str(tmp_path),
        "--no-graph",
        "--analyzer",
        "replay",
        "--replay-dir",
        str(tmp_path),
    )

    assert code == 0 and data["written"] == 0
    assert len(calls) == 1


def test_generate_writes_a_new_skill_without_overwrite(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    code, data = generate_signup(capsys, root)
    assert code == 0 and data["written"] == 1 and data["exists"] == 0


def test_generate_leaves_an_existing_skill_alone_without_overwrite(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    skill_md = root / "skills" / "shop-signup" / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
    code, data = generate_signup(capsys, root)
    assert code == 0
    assert (data["written"], data["exists"]) == (0, 1)
    assert data["results"][0]["status"] == "exists"
    assert "hand edit" in skill_md.read_text(encoding="utf-8")


def test_generate_recreates_an_existing_skill_with_overwrite(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    skill_md = root / "skills" / "shop-signup" / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
    code, data = generate_signup(capsys, root, "--overwrite")
    assert code == 0 and data["written"] == 1
    assert "hand edit" not in skill_md.read_text(encoding="utf-8")


def test_generate_reports_an_existing_skill_before_any_analysis(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    # An analysis from this folder would fail, so `exists` proves none was attempted.
    code, data = generate_signup(capsys, root, replay=str(tmp_path / "no-analyses-here"))
    assert code == 0 and data["results"][0]["status"] == "exists"


def test_generate_restores_routes_when_a_rename_writes_nothing(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    generate_signup(capsys, root, "--name", "renamed-signup")
    routes = root / f".{TOOL_NAME}" / "routes.json"
    before = routes.read_text(encoding="utf-8")
    _, data = generate_signup(capsys, root, "--name", "shop-signup")
    assert data["results"][0]["status"] == "exists"
    assert routes.read_text(encoding="utf-8") == before


def test_generate_text_output_tells_the_agent_to_ask(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    replay = str(FIXTURES / "react-router-spa" / "analyses")
    main(
        [
            "generate",
            "--route",
            "/signup",
            "--root",
            str(root),
            "--analyzer",
            "replay",
            "--replay-dir",
            replay,
            "--no-graph",
        ]
    )
    out = capsys.readouterr().out
    assert "Ask the developer" in out and "--overwrite" in out


def test_prepare_reports_whether_the_skill_exists(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    prepare = ("prepare", "--route", "/signup", "--root", str(root), "--no-graph")
    _, fresh = run(capsys, *prepare)
    assert fresh["skill_exists"] is False
    generate_signup(capsys, root)
    _, again = run(capsys, *prepare)
    assert again["skill_exists"] is True
    assert again["skill_folder"].endswith("shop-signup")


def test_install_downloads_chromium_for_xy(tmp_path, capsys, monkeypatch):
    calls = []

    def install_chromium():
        calls.append(1)
        return "chromium installed"

    monkeypatch.setattr(skillgen_cli, "install_chromium", install_chromium)
    code, data = run(capsys, "install", "--target", str(tmp_path))
    assert code == 0 and calls == [1] and data["chromium"] == "chromium installed"


def test_install_chromium_explains_a_missing_probe_extra(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert skillgen_cli.install_chromium().startswith("chromium skipped")


def page_fields(root, skill="shop-signup"):
    return json.loads((root / f".{TOOL_NAME}" / "pages" / skill / "page.json").read_text("utf-8"))


def test_generate_ignores_a_saved_probe_capture_without_xy(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    before = page_fields(root)["fields"]
    # The failure seen on a page whose form starts hidden: a capture of junk controls.
    capture = root / f".{TOOL_NAME}" / "pages" / "shop-signup" / "probe" / "probe.json"
    capture.parent.mkdir(parents=True, exist_ok=True)
    junk = {"key": "field_2_2", "label": "", "selector": "select", "strategy": "native-select"}
    capture.write_text(json.dumps({"url": "x", "title": "x", "fields": [junk]}), "utf-8")
    code, data = generate_signup(capsys, root, "--overwrite")
    assert code == 0 and data["written"] == 1
    assert page_fields(root)["fields"] == before


def fake_measurement(root, monkeypatch):
    """Make --xy measure every steady field of the skill, and record the open steps."""
    seen = []

    def measure_page_layout(workspace, settings, entry, page):
        seen.append(page.open_steps)
        boxes = tuple(
            (spec.key, Box(300, 100 + index * 80, 600, 40))
            for index, spec in enumerate(page.fields)
            if not spec.group
        )
        return Layout(viewport_width=1280, viewport_height=900, boxes=boxes)

    monkeypatch.setattr(probe_runner, "measure_page_layout", measure_page_layout)
    # No dev server runs in tests; the check before any work is tested on its own.
    monkeypatch.setattr(probe_runner, "find_xy_need", lambda settings: None)
    page = page_fields(root)
    return sum(1 for spec in page["fields"].values() if not spec.get("group")), seen


def test_generate_with_xy_adds_x_and_y_without_removing_fields(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    normal = page_fields(root)
    expected, _ = fake_measurement(root, monkeypatch)
    code, data = generate_signup(capsys, root, "--xy", "--url", "http://localhost:9", "--overwrite")
    assert code == 0 and data["written"] == 1
    page = page_fields(root)
    assert page["fields"] == normal["fields"]
    assert data["results"][0]["measured_fields"] == expected
    assert len(page["layout"]["boxes"]) == expected


def test_generate_without_xy_measures_nothing(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    _, seen = fake_measurement(root, monkeypatch)
    _, data = generate_signup(capsys, root, "--overwrite")
    assert seen == [] and data["results"][0]["measured_fields"] == 0
    assert "layout" not in page_fields(root)


def test_generate_open_steps_are_saved_and_reach_the_probe(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    _, seen = fake_measurement(root, monkeypatch)
    step = 'button[title="Page settings"]'
    generate_signup(
        capsys, root, "--xy", "--url", "http://localhost:9", "--open", step, "--overwrite"
    )
    routes = json.loads((root / f".{TOOL_NAME}" / "routes.json").read_text("utf-8"))
    entry = next(e for e in routes["routes"] if e["route"] == "/signup")
    assert entry["open"] == [step] and seen == [(step,)]
    assert page_fields(root)["open"] == [step]


def test_generate_open_needs_one_route(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    code, data = run(
        capsys,
        "generate",
        "--all",
        "--root",
        str(root),
        "--open",
        "#x",
        "--analyzer",
        "replay",
        "--replay-dir",
        str(tmp_path),
        "--no-graph",
    )
    assert code != 0 and "--open" in data["error"]


def test_layout_measurer_does_nothing_without_xy(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    arguments = build_parser().parse_args(["generate", "--all", "--root", str(root)])
    workspace = skillgen_cli.open_workspace(arguments)
    entry = workspace.read_routes().find("/signup")
    assert entry is not None
    normal = replace(workspace.read_settings(), should_probe=False)
    assert skillgen_cli._layout_measurer(workspace, normal, entry) is None
    with_xy = replace(normal, should_probe=True, app_url="http://localhost:9")
    assert skillgen_cli._layout_measurer(workspace, with_xy, entry) is not None


def replay_with_open(tmp_path, steps):
    """A copy of the fixture's analyses where /signup says how its form opens."""
    folder = tmp_path / "replay"
    folder.mkdir()
    for source in (FIXTURES / "react-router-spa" / "analyses").glob("*.json"):
        data = json.loads(source.read_text("utf-8"))
        if source.stem == "signup":
            data["open"] = {"steps": steps}
        (folder / source.name).write_text(json.dumps(data), "utf-8")
    return str(folder)


def test_generate_uses_open_steps_from_the_code_analysis(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    _, seen = fake_measurement(root, monkeypatch)
    replay = replay_with_open(tmp_path, ["text:Account settings"])
    generate_signup(
        capsys, root, "--xy", "--url", "http://localhost:9", "--overwrite", replay=replay
    )
    assert seen == [("text:Account settings",)]
    assert page_fields(root)["open"] == ["text:Account settings"]


def test_generate_open_flag_wins_over_the_code_analysis(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    _, seen = fake_measurement(root, monkeypatch)
    replay = replay_with_open(tmp_path, ["text:Account settings"])
    generate_signup(
        capsys,
        root,
        "--xy",
        "--url",
        "http://localhost:9",
        "--open",
        "text:Mine",
        "--overwrite",
        replay=replay,
    )
    assert seen == [("text:Mine",)]
    assert page_fields(root)["open"] == ["text:Mine"]


def test_generate_normal_run_keeps_the_last_x_and_y(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    expected, _ = fake_measurement(root, monkeypatch)
    generate_signup(capsys, root, "--xy", "--url", "http://localhost:9", "--overwrite")
    _, data = generate_signup(capsys, root, "--overwrite")
    (result,) = data["results"]
    assert result["status"] == "written" and result["measured_fields"] == expected
    assert result["problems"][0].startswith(f"x/y kept from the last --xy run for {expected}")
    assert len(page_fields(root)["layout"]["boxes"]) == expected


def test_generate_says_nothing_when_x_and_y_is_kept(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    fake_measurement(root, monkeypatch)
    generate_signup(capsys, root, "--xy", "--url", "http://localhost:9", "--overwrite")
    _, data = generate_signup(capsys, root, "--xy", "--url", "http://localhost:9", "--overwrite")
    assert data["results"][0]["problems"] == []


SIGNUP_ANALYSIS = FIXTURES / "react-router-spa" / "analyses" / "signup.json"


def generate_signup_with_claude(capsys, root, *extra):
    return run(
        capsys,
        "generate",
        "--route",
        "/signup",
        "--root",
        str(root),
        "--analyzer",
        "claude-code",
        "--no-graph",
        *extra,
    )


def fake_claude(monkeypatch, answer):
    """Make headless Claude Code answer with `answer` (a dict or an error), counting calls."""
    calls = []

    def analyze(self, request):
        calls.append(request.route)
        if isinstance(answer, Exception):
            raise answer
        return json.loads(json.dumps(answer))

    monkeypatch.setattr(ClaudeCodeAnalyzer, "analyze", analyze)
    return calls


def test_generate_hands_the_analysis_to_the_agent_when_claude_cannot_run(
    tmp_path, capsys, monkeypatch
):
    root = make_shop(tmp_path, capsys)
    fake_claude(monkeypatch, AnalysisError("Claude Code failed on /signup: not signed in"))
    code, data = generate_signup_with_claude(capsys, root)
    (result,) = data["results"]
    assert code == EXIT_NEEDS and data["ok"] is False and data["needs"] == 1
    assert result["status"] == "needs" and result["next"]["action"] == "analyse"
    assert result["next"]["prompt"].endswith("prompt.md")
    assert Path(result["next"]["prompt"]).is_file()
    assert "--analyzer claude-code" in result["next"]["then"]
    assert not (root / "skills" / "shop-signup").exists()


def test_generate_continues_from_the_analysis_the_agent_wrote(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    calls = fake_claude(monkeypatch, AnalysisError("not signed in"))
    _, data = generate_signup_with_claude(capsys, root)
    write = Path(data["results"][0]["next"]["write"])
    write.write_text(SIGNUP_ANALYSIS.read_text("utf-8"), "utf-8")
    code, data = generate_signup_with_claude(capsys, root)
    assert code == 0 and data["written"] == 1 and calls == ["/signup"]


def test_generate_reuses_an_analysis_while_prompt_and_code_are_unchanged(
    tmp_path, capsys, monkeypatch
):
    root = make_shop(tmp_path, capsys)
    calls = fake_claude(monkeypatch, json.loads(SIGNUP_ANALYSIS.read_text("utf-8")))
    generate_signup_with_claude(capsys, root)
    code, data = generate_signup_with_claude(capsys, root, "--overwrite")
    assert code == 0 and data["written"] == 1 and calls == ["/signup"]


def test_generate_xy_without_an_address_writes_the_skill_then_asks(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    calls = fake_claude(monkeypatch, json.loads(SIGNUP_ANALYSIS.read_text("utf-8")))
    code, data = generate_signup_with_claude(capsys, root, "--xy")
    (result,) = data["results"]
    assert code == EXIT_NEEDS and result["status"] == "written" and calls == ["/signup"]
    assert (root / "skills" / "shop-signup" / "SKILL.md").is_file()
    assert result["next"]["need"] == "url" and "address" in result["next"]["ask"]
    assert result["next"]["then"].endswith("--overwrite --url '<url>'")
    # Continuing reuses the analysis: Claude is not asked again.
    generate_signup_with_claude(capsys, root, "--xy", "--overwrite")
    assert calls == ["/signup"]


def test_generate_xy_stops_when_the_dev_server_is_down(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    monkeypatch.setattr(
        probe_runner, "find_xy_need", lambda settings: (Need.SERVER, settings.app_url)
    )
    code, data = generate_signup(capsys, root, "--xy", "--url", "http://localhost:9")
    (result,) = data["results"]
    assert code == EXIT_NEEDS and result["next"]["need"] == "server"
    assert "http://localhost:9" in result["next"]["ask"]


def test_generate_writes_the_skill_and_offers_a_sign_in(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    url = "http://localhost:9/signup"

    def measure_page_layout(workspace, settings, entry, page):
        raise ActionNeededError(Need.LOGIN, url, f"{url} showed a sign-in page")

    monkeypatch.setattr(probe_runner, "measure_page_layout", measure_page_layout)
    monkeypatch.setattr(probe_runner, "find_xy_need", lambda settings: None)
    code, data = generate_signup(capsys, root, "--xy", "--url", "http://localhost:9")
    (result,) = data["results"]
    assert code == EXIT_NEEDS and result["status"] == "written"
    assert (root / "skills" / "shop-signup" / "SKILL.md").is_file()
    assert result["next"]["need"] == "login"
    assert result["next"]["run"].startswith(f"{TOOL_NAME} login --url {url} --root ")
    assert result["next"]["then"].endswith("--overwrite")


def test_generate_existing_skill_offers_to_overwrite(tmp_path, capsys):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    code, data = generate_signup(capsys, root)
    (result,) = data["results"]
    assert code == 0 and result["status"] == "exists"
    assert result["next"]["need"] == "overwrite" and result["next"]["then"].endswith("--overwrite")


def test_generate_failed_checks_leave_the_skill_and_page_as_they_were(
    tmp_path, capsys, monkeypatch
):
    root = make_shop(tmp_path, capsys)
    generate_signup(capsys, root)
    page = root / f".{TOOL_NAME}" / "pages" / "shop-signup" / "page.json"
    skill = root / "skills" / "shop-signup" / "SKILL.md"
    before = (page.read_bytes(), skill.read_bytes())
    monkeypatch.setattr("skillgen.pipeline.find_skill_problems", lambda *_: ["broken"])
    code, data = generate_signup(capsys, root, "--overwrite")
    assert code != 0 and data["invalid"] == 1
    assert (page.read_bytes(), skill.read_bytes()) == before


def measure_only_when_opened(monkeypatch, url="http://localhost:9/signup"):
    """Make --xy see the fields only after an open step, like a collapsed panel."""
    seen = []

    def measure_page_layout(workspace, settings, entry, page):
        seen.append(page.open_steps)
        if not page.open_steps:
            raise ActionNeededError(Need.OPEN, url, f"no field was on screen at {url}")
        boxes = tuple(
            (spec.key, Box(300, 100 + index * 80, 600, 40))
            for index, spec in enumerate(page.fields)
            if not spec.group
        )
        return Layout(viewport_width=1280, viewport_height=900, boxes=boxes)

    monkeypatch.setattr(probe_runner, "measure_page_layout", measure_page_layout)
    monkeypatch.setattr(probe_runner, "find_xy_need", lambda settings: None)
    return seen


def replay_with_inferred_open(tmp_path, steps):
    folder = tmp_path / "replay-inferred"
    folder.mkdir()
    for source in (FIXTURES / "react-router-spa" / "analyses").glob("*.json"):
        data = json.loads(source.read_text("utf-8"))
        if source.stem == "signup":
            data["open"] = {"steps": steps, "inferred": True}
        (folder / source.name).write_text(json.dumps(data), "utf-8")
    return str(folder)


def test_generate_xy_proves_a_deduced_open_step_in_the_browser(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    seen = measure_only_when_opened(monkeypatch)
    replay = replay_with_inferred_open(tmp_path, ["text:Page settings"])
    code, data = generate_signup(capsys, root, "--xy", "--url", "http://localhost:9", replay=replay)
    (result,) = data["results"]
    assert code == 0 and result["measured_fields"] > 0 and "next" not in result
    assert seen == [(), ("text:Page settings",)]
    assert page_fields(root)["open"] == ["text:Page settings"]
    _, questions = run(capsys, "questions", "--root", str(root))
    assert not [q for q in questions["questions"] if q["subject"] == "open"]


def test_generate_xy_never_tries_a_risky_open_step(tmp_path, capsys, monkeypatch):
    root = make_shop(tmp_path, capsys)
    seen = measure_only_when_opened(monkeypatch)
    replay = replay_with_inferred_open(tmp_path, ["text:Delete page"])
    code, data = generate_signup(capsys, root, "--xy", "--url", "http://localhost:9", replay=replay)
    (result,) = data["results"]
    assert seen == [()] and code == EXIT_NEEDS and result["status"] == "written"
    assert result["next"]["need"] == "open"
    assert result["next"]["then"].endswith("--overwrite --open 'text:<label>'")


def test_describe_export_use_warns_a_plain_multi_page_zip_will_be_refused():
    lines = describe_export_use("", "", 3)
    assert "export --one-skill" in lines[0] and "3 skills in one archive" in lines[0]
    assert describe_export_use("", "", 1) == []
    assert describe_export_use("acme", "", 3)[0].startswith("One skill named acme")
