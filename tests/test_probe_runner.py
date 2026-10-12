"""The probe: pure classification here, and a real probe of the bench page (-m browser)."""

from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.request
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from skillgen.config import Environment, Settings
from skillgen.errors import Need, ProbeError, UnsafeEnvironmentError
from skillgen.model.page import Strategy
from skillgen.model.route import RouteEntry
from skillgen.probe.capture import probed_page_to_dict
from skillgen.probe.runner import (
    CHROMIUM_VARIABLE,
    choose_reveal_value,
    find_open_steps,
    find_xy_need,
    is_answering,
    is_on_open,
    measure_boxes,
    plan_stages,
    probe_route,
    probe_url,
    values_before,
)
from skillgen.workspace import Workspace
from tests.conftest import assert_golden
from tests.helpers import BENCH, load_bench_page, load_script, load_wizard_page

BENCH_URL = "http://localhost:8765/apply"


def test_probe_route_refuses_production(tmp_path):
    settings = Settings(app_url="https://app.example.com", environment=Environment.PRODUCTION)
    with pytest.raises(UnsafeEnvironmentError):
        probe_route(Workspace(tmp_path), settings, RouteEntry("/x", "x"))


def test_probe_route_needs_concrete_route(tmp_path):
    settings = Settings(app_url="https://app.example.com")
    with pytest.raises(ProbeError, match="parameters"):
        probe_route(Workspace(tmp_path), settings, RouteEntry("/items/:id/edit", "x"))


@pytest.fixture(scope="module")
def bench_server() -> Iterator[str]:
    serve = load_script(BENCH / "serve.py")
    server = serve.make_server("127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://localhost:{server.server_address[1]}"
    server.shutdown()


@pytest.mark.browser
def test_probe_url_reads_bench_page_without_saving(bench_server, update_golden, monkeypatch):
    pytest.importorskip("playwright.sync_api")
    if Path("/opt/pw-browsers/chromium").exists():
        monkeypatch.setenv(CHROMIUM_VARIABLE, "/opt/pw-browsers/chromium")
    probed = probe_url(f"{bench_server}/apply")
    by_key = {f.key: f for f in probed.fields}
    assert by_key["country"].strategy is Strategy.NATIVE_SELECT and by_key["country"].is_proven
    assert by_key["statement"].strategy is Strategy.RICH_TEXT and by_key["statement"].is_proven
    assert by_key["skills"].strategy is Strategy.ARIA_LISTBOX
    assert by_key["references_name"].is_repeated
    assert {(c.controller, c.value) for c in probed.conditions} == {("account_type", "Company")}
    assert [(d.controller, d.target, d.is_async) for d in probed.dependencies] == [
        ("country", "region", True)
    ]
    assert probed.submit_selector == "#submit"
    submissions = json.loads(urllib.request.urlopen(f"{bench_server}/api/submissions").read())
    assert submissions == [], "the probe must never create records"
    capture = probed_page_to_dict(probed) | {"url": BENCH_URL}
    assert_golden(
        BENCH / "probe.json",
        json.dumps(capture, indent=2, ensure_ascii=False) + "\n",
        update_golden,
    )


def test_find_open_steps_prefers_the_developers_own(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_page(replace(load_bench_page(), open_steps=("text:From code",)))
    mine = RouteEntry("/apply", "bench-apply", open_steps=("text:Mine",))
    assert find_open_steps(workspace, mine) == ("text:Mine",)


def test_find_open_steps_falls_back_to_the_code_analysis(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_page(replace(load_bench_page(), open_steps=("text:From code",)))
    assert find_open_steps(workspace, RouteEntry("/apply", "bench-apply")) == ("text:From code",)


def test_find_open_steps_is_empty_without_either(tmp_path):
    assert find_open_steps(Workspace(tmp_path), RouteEntry("/apply", "bench-apply")) == ()


def test_find_xy_need_is_nothing_without_xy():
    assert find_xy_need(Settings(should_probe=False)) is None


def test_find_xy_need_asks_for_an_address_first():
    assert find_xy_need(Settings(should_probe=True)) == (Need.URL, "")


def test_find_xy_need_says_when_the_dev_server_is_down(monkeypatch):
    monkeypatch.setattr("skillgen.probe.runner.importlib.util.find_spec", lambda name: object())
    monkeypatch.setattr("skillgen.probe.runner.is_chromium_ready", lambda: True)
    monkeypatch.setattr("skillgen.probe.runner.is_answering", lambda url: False)
    settings = Settings(should_probe=True, app_url="http://localhost:3000")
    assert find_xy_need(settings) == (Need.SERVER, "http://localhost:3000")


def test_find_xy_need_says_when_chromium_is_missing(monkeypatch):
    monkeypatch.setattr("skillgen.probe.runner.importlib.util.find_spec", lambda name: object())
    monkeypatch.setattr("skillgen.probe.runner.is_chromium_ready", lambda: False)
    settings = Settings(should_probe=True, app_url="http://localhost:3000")
    assert find_xy_need(settings) == (Need.CHROMIUM, "")


def test_is_answering_tells_an_open_port_from_a_closed_one():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        assert is_answering(f"http://127.0.0.1:{port}/x")
    assert not is_answering(f"http://127.0.0.1:{port}/x", timeout_seconds=1)


class _SignInHandler(http.server.BaseHTTPRequestHandler):
    """/form sends the browser to a sign-in page; /plain is the form itself."""

    def do_GET(self) -> None:
        if self.path == "/form":
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        body = b"<input type=password>" if self.path == "/login" else b"<input id=name>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@pytest.mark.browser
def test_measure_boxes_tells_a_sign_in_page_from_the_form(monkeypatch):
    pytest.importorskip("playwright")
    if Path("/opt/pw-browsers/chromium").exists():
        monkeypatch.setenv(CHROMIUM_VARIABLE, "/opt/pw-browsers/chromium")
    server = http.server.HTTPServer(("127.0.0.1", 0), _SignInHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        signed_out = measure_boxes(f"{base}/form", None, (), ["#name"])
        form = measure_boxes(f"{base}/plain", None, (), ["#name"])
    finally:
        server.shutdown()
    assert signed_out.is_sign_in and signed_out.boxes == {}
    assert not form.is_sign_in and "#name" in form.boxes


def test_plan_stages_reaches_each_view_then_each_conditional_field():
    stages = plan_stages(load_wizard_page())
    assert [stage.label for stage in stages] == [
        "Address tab",
        "Step 2",
        "Contact dialog",
        "Step 3",
        "laptop (when work_location is set)",
    ]
    assert all(stage.call and not stage.call.startswith("await ") for stage in stages)
    assert '"work_location":"Remote"' in stages[-1].call


def test_values_before_keeps_only_earlier_parts():
    page = load_wizard_page()
    examples = {"first_name": "Ada", "city": "X", "department": "Sales", "agree": True}
    assert values_before(page, examples, 1) == {"first_name": "Ada", "city": "X"}
    assert values_before(page, examples, -1) == {}


def test_choose_reveal_value_meets_the_condition():
    page = load_wizard_page()
    laptop = next(spec for spec in page.fields if spec.key == "laptop")
    assert choose_reveal_value(page, laptop, {}) == "Remote"


@pytest.mark.browser
def test_measure_boxes_measures_every_view_and_revealed_field(bench_server, monkeypatch):
    if Path("/opt/pw-browsers/chromium").exists():
        monkeypatch.setenv(CHROMIUM_VARIABLE, "/opt/pw-browsers/chromium")
    page = load_wizard_page()
    first = [spec.selector for spec in page.fields if is_on_open(page, spec)]
    found = measure_boxes(f"{bench_server}/wizard", None, (), first, plan_stages(page))
    assert set(found.boxes) == {spec.selector for spec in page.fields}
    assert not found.is_sign_in
