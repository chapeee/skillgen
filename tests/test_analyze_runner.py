import json
import subprocess
from typing import Any

import pytest

from skillgen.analyze.prompt import (
    AnalysisRequest,
)
from skillgen.analyze.runner import (
    ClaudeCall,
    ClaudeCodeAnalyzer,
    FileAnalyzer,
    ReplayAnalyzer,
    build_claude_command,
    check_analysis,
    describe_claude_failure,
    is_limit_reached,
    list_routes_with_claude,
    parse_claude_output,
    prepare_claude_run,
    schema_for_claude,
)
from skillgen.errors import AnalysisError
from tests.conftest import FIXTURES

REQUEST = AnalysisRequest(
    route="/signup", skill="shop-signup", app_name="Shop", slice_files=("a.tsx", "b.tsx")
)
GOOD = {"has_form": False, "title": "x", "fields": []}


def test_parse_claude_output_prefers_structured_output():
    assert parse_claude_output(json.dumps({"structured_output": GOOD, "result": "x"})) == GOOD


def test_parse_claude_output_reads_fenced_result():
    stdout = json.dumps({"result": "```json\n" + json.dumps(GOOD) + "\n```"})
    assert parse_claude_output(stdout) == GOOD


@pytest.mark.parametrize(
    "stdout",
    [
        "not json",
        json.dumps({"is_error": True, "result": "boom"}),
        json.dumps({"result": "prose"}),
        "{}",
    ],
)
def test_parse_claude_output_errors(stdout):
    with pytest.raises(AnalysisError):
        parse_claude_output(stdout)


def test_check_analysis_rejects_off_schema():
    with pytest.raises(AnalysisError, match="schema"):
        check_analysis({"fields": "no"}, "test")


def test_build_claude_command_is_read_only():
    command = build_claude_command("claude", "page-analysis", "sonnet")
    assert command[:2] == ["claude", "-p"]
    assert command[command.index("--allowedTools") + 1 : command.index("--allowedTools") + 4] == [
        "Read",
        "Grep",
        "Glob",
    ]
    assert json.loads(command[command.index("--json-schema") + 1])["title"].startswith(
        "Page analysis"
    )
    assert command[-2:] == ["--model", "sonnet"]


def test_claude_code_analyzer_runs_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/bin/claude")
    completed = subprocess.CompletedProcess([], 0, json.dumps({"structured_output": GOOD}), "")
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: completed)
    assert ClaudeCodeAnalyzer(tmp_path).analyze(REQUEST) == GOOD


def test_claude_code_analyzer_runs_resolved_path_with_prompt_on_stdin(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/opt/bin/claude")
    seen: dict[str, Any] = {}  # subprocess.run keyword arguments of mixed types

    def run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess([], 0, json.dumps({"structured_output": GOOD}), "")

    monkeypatch.setattr("subprocess.run", run)
    ClaudeCodeAnalyzer(tmp_path).analyze(REQUEST)
    assert seen["command"][0] == "/opt/bin/claude"
    assert "/signup" in seen["input"] and "/signup" not in " ".join(seen["command"])
    assert seen["encoding"] == "utf-8"


def test_prepare_claude_run_moves_schema_into_prompt_for_cmd_shim():
    call = ClaudeCall("List the routes.", "route-listing", "sonnet")
    command, prompt = prepare_claude_run("C:/npm/claude.CMD", call)
    assert "--json-schema" not in command and command[-2:] == ["--model", "sonnet"]
    assert prompt.startswith("List the routes.") and '"routes"' in prompt
    command, prompt = prepare_claude_run("C:/bin/claude.exe", call)
    assert "--json-schema" in command and prompt == "List the routes."


def test_claude_code_analyzer_reports_start_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/bin/claude")

    def run(*args, **kwargs):
        raise FileNotFoundError(2, "The system cannot find the file specified")

    monkeypatch.setattr("subprocess.run", run)
    with pytest.raises(AnalysisError, match="could not start"):
        ClaudeCodeAnalyzer(tmp_path).analyze(REQUEST)


def test_claude_code_analyzer_reports_missing_cli(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(AnalysisError, match="not on PATH"):
        ClaudeCodeAnalyzer(tmp_path).analyze(REQUEST)


def test_claude_code_analyzer_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/bin/claude")
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: subprocess.CompletedProcess([], 1, "", "auth needed")
    )
    with pytest.raises(AnalysisError, match="auth needed"):
        ClaudeCodeAnalyzer(tmp_path).analyze(REQUEST)


def test_file_analyzer_reads_written_analysis(tmp_path):
    (tmp_path / "shop-signup").mkdir()
    (tmp_path / "shop-signup" / "analysis.json").write_text(json.dumps(GOOD))
    assert FileAnalyzer(tmp_path).analyze(REQUEST) == GOOD
    with pytest.raises(AnalysisError, match="no analysis"):
        FileAnalyzer(tmp_path / "x").analyze(REQUEST)


def test_replay_analyzer_reads_by_route_slug():
    analysis = ReplayAnalyzer(FIXTURES / "react-router-spa" / "analyses").analyze(REQUEST)
    assert analysis["title"] == "Create your account"


def test_schema_for_claude_drops_meta_schema_key():
    schema = schema_for_claude()
    assert "$schema" not in schema and schema["required"] == ["has_form", "title", "fields"]


def test_list_routes_with_claude_validates_answer(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/bin/claude")
    answer = {"structured_output": {"routes": [{"route": "/signup", "entry_files": ["a.html"]}]}}
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: subprocess.CompletedProcess([], 0, json.dumps(answer), "")
    )
    assert list_routes_with_claude(tmp_path, "list") == [
        {"route": "/signup", "entry_files": ["a.html"]}
    ]
    bad = {"structured_output": {"routes": [{"route": "no-slash", "entry_files": []}]}}
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: subprocess.CompletedProcess([], 0, json.dumps(bad), "")
    )
    with pytest.raises(AnalysisError, match="route list"):
        list_routes_with_claude(tmp_path, "list")


def test_describe_claude_failure_reads_the_reason_from_the_json_result():
    stdout = json.dumps(
        {"is_error": True, "result": "Failed to authenticate: OAuth session expired"}
    )
    reason = describe_claude_failure(stdout, "")
    assert reason.startswith("Failed to authenticate: OAuth session expired")
    assert "run `claude` once and sign in" in reason


def test_describe_claude_failure_keeps_a_limit_message_whole():
    """A limit is classified by `is_limit_reached`, so the reason is passed through.

    The run then waits for the reset instead of handing the route to the agent, which
    would spend much more of the same limit.
    """
    told = "You've hit your session limit, resets 8:40pm"
    reason = describe_claude_failure(json.dumps({"result": told}), "")
    assert reason == told
    assert is_limit_reached(reason)


def test_describe_claude_failure_falls_back_to_the_error_stream():
    assert describe_claude_failure("not json", "boom") == "boom"
    assert describe_claude_failure("", "") == "no output"
