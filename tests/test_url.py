"""URL-only generation, including a real browser with no app source checkout."""

from __future__ import annotations

import http.server
import json
import threading
from dataclasses import replace
from unittest.mock import Mock

import pytest

from skillgen import cli, pipeline
from skillgen.errors import ProbeError
from skillgen.generate.user_rules import USER_START
from skillgen.model.facts import Source
from skillgen.model.page import Box, Strategy, ValueType
from skillgen.model.probe import ProbedField, ProbedPage
from skillgen.probe import readonly
from skillgen.workspace import Workspace


@pytest.fixture
def observed():
    return ProbedPage(
        url="https://example.com/form?type=one#details",
        title="Example form",
        fields=(
            ProbedField(
                key="email",
                label="Email",
                selector="#email",
                strategy=Strategy.NATIVE_INPUT,
                value_type=ValueType.EMAIL,
                is_required=True,
                box=Box(20, 40, 200, 30),
            ),
        ),
        submit_selector="#save",
        submit_label="Save",
        viewport_width=1280,
        viewport_height=900,
    )


def _forbid_code(*args, **kwargs):
    pytest.fail("URL mode must never call code discovery, Graphify, or analysis")


@pytest.fixture
def no_code(monkeypatch):
    for module in (cli, pipeline):
        for name in (
            "try_load_graph",
            "load_graph",
            "load_graphify_graph",
            "discover_routes",
            "find_route_candidates",
            "prepare_route",
            "analyze_route",
            "read_source_commit",
        ):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, _forbid_code)


def _generate(tmp_path, capsys, *extra):
    result = cli.main(
        [
            "generate-url",
            "https://example.com/form",
            "--name",
            "example-form",
            "--root",
            str(tmp_path),
            "--json",
            *extra,
        ]
    )
    return result, json.loads(capsys.readouterr().out)


def test_url_generates_without_source_and_reuses_validation_export(
    tmp_path,
    capsys,
    monkeypatch,
    observed,
    no_code,
):
    monkeypatch.setattr(readonly, "read_url", lambda url: observed)
    result, data = _generate(tmp_path, capsys)
    assert result == 0 and data["written"] == 1
    assert data["results"][0]["measured_fields"] == 1
    workspace = Workspace(tmp_path)
    page = workspace.read_page("example-form")
    assert page is not None and page.layout is not None
    assert page.route == "/form?type=one#details"
    assert page.app_url == "https://example.com"
    assert page.fields[0].provenance.sources == (Source.RUNTIME_PROBED,)
    assert page.fields[0].is_required and not page.is_verified
    assert page.source_commit == ""
    text = (tmp_path / "skills/example-form/SKILL.md").read_text(encoding="utf-8")
    assert observed.url in text and "read from its code" not in text
    assert (tmp_path / "skills/example-form/scripts/fill.js").is_file()
    for filename in ("analysis.json", "slice.json", "prompt.md"):
        assert not (workspace.page_folder("example-form") / filename).exists()
    assert not list(workspace.cache_folder.iterdir())
    assert cli.main(["validate", "--root", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert cli.main(["export", "--root", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]


def test_url_optional_fields_are_not_marked_verified(tmp_path, capsys, monkeypatch, observed):
    probe = replace(observed, fields=(replace(observed.fields[0], is_required=False),))
    monkeypatch.setattr(readonly, "read_url", lambda url: probe)
    result, data = _generate(tmp_path, capsys)
    assert result == 0 and not data["results"][0]["verified"]
    page = Workspace(tmp_path).read_page("example-form")
    assert page is not None and not page.is_verified


def test_url_overwrite_guard_precedes_browser_and_keeps_user_notes(
    tmp_path,
    capsys,
    monkeypatch,
    observed,
):
    reader = Mock(return_value=observed)
    monkeypatch.setattr(readonly, "read_url", reader)
    assert _generate(tmp_path, capsys)[0] == 0
    path = tmp_path / "skills/example-form/SKILL.md"
    text = path.read_text(encoding="utf-8").replace(USER_START, USER_START + "\nKeep my note.")
    path.write_text(text, encoding="utf-8")
    assert _generate(tmp_path, capsys)[1]["exists"] == 1
    assert reader.call_count == 1 and path.read_text(encoding="utf-8") == text
    assert _generate(tmp_path, capsys, "--overwrite")[1]["written"] == 1
    assert reader.call_count == 2 and "Keep my note." in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("fields", [(), ("hidden",), ("repeated",)])
def test_url_no_usable_form_does_not_write_skill(tmp_path, capsys, monkeypatch, observed, fields):
    captured = (
        ()
        if not fields
        else (
            replace(
                observed.fields[0],
                is_visible=fields != ("hidden",),
                is_repeated=fields == ("repeated",),
            ),
        )
    )
    monkeypatch.setattr(readonly, "read_url", lambda url: replace(observed, fields=captured))
    assert _generate(tmp_path, capsys)[1]["no_form"] == 1
    assert not (tmp_path / "skills").exists()


@pytest.mark.parametrize(
    "url,name",
    [
        ("file:///tmp/page", "valid"),
        ("https://example.com", "../escape"),
        ("https://example.com", "Bad Name"),
        ("", "valid"),
    ],
)
def test_url_rejects_invalid_input_before_browser(tmp_path, capsys, monkeypatch, url, name):
    monkeypatch.setattr(readonly, "read_url", _forbid_code)
    result = cli.main(["generate-url", url, "--name", name, "--root", str(tmp_path), "--json"])
    assert result == 2 and not json.loads(capsys.readouterr().out)["ok"]
    assert not (tmp_path / "skills").exists()


def test_url_browser_failure_writes_no_skill(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(readonly, "read_url", Mock(side_effect=ProbeError("unreachable")))
    result, data = _generate(tmp_path, capsys)
    assert result == 2 and "unreachable" in data["error"]
    assert not (tmp_path / "skills").exists()


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"])
def test_readonly_guard_blocks_write_requests(method):
    route = Mock()
    route.request.method = method
    readonly._guard_request(route)
    assert route.continue_.call_count == int(method in ("GET", "HEAD", "OPTIONS"))
    assert route.abort.call_count == int(method not in ("GET", "HEAD", "OPTIONS"))


@pytest.fixture
def website():
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(("GET", self.path))
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<!doctype html><title>Read only demo</title>
                <form action='/saved'><label>Email<input id='email' type='email' required></label>
                <label>Category<select id='category'><option>One</option><option>Two</option>
                </select></label><input id='secret' type='hidden'>
                <input id='later' style='display:none'><button type='submit'>Save</button></form>
                <script>
                ['click','input','change','submit'].forEach(function(event) {
                  document.addEventListener(event, function() { fetch('/interaction'); });
                });
                fetch('/write', {method:'POST', body:'must be blocked'}).catch(function() {});
                </script>""")

        def do_POST(self):
            requests.append(("POST", self.path))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/form", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.browser
def test_url_real_browser_generates_without_code_or_interactions(
    tmp_path, capsys, website, no_code
):
    pytest.importorskip("playwright.sync_api")
    url, requests = website
    assert not list(tmp_path.iterdir())
    result = cli.main(
        [
            "generate-url",
            url,
            "--name",
            "website-form",
            "--root",
            str(tmp_path),
            "--json",
        ]
    )
    data = json.loads(capsys.readouterr().out)
    assert result == 0, data
    assert data["written"] == 1 and data["results"][0]["measured_fields"] == 2
    page = Workspace(tmp_path).read_page("website-form")
    assert page is not None and page.layout is not None
    assert {field.key for field in page.fields} == {"email", "category"}
    assert all(box.width > 0 and box.height > 0 for _, box in page.layout.boxes)
    assert not page.is_verified
    assert all(method == "GET" and path != "/interaction" for method, path in requests)
    assert not any(path in ("/write", "/saved") for _, path in requests)
