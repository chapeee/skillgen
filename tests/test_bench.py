"""The bench: its generated skill stays current, its cases are sound, and fill.js
fills the bench page for every case in a real browser (pytest -m browser)."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from skillgen.assets import read_fill_engine
from skillgen.compile.merge import MergeInput, build_page_model
from skillgen.generate.folder import build_skill_files
from skillgen.model.serialize import page_to_dict
from skillgen.probe.capture import probed_page_from_dict
from skillgen.validate.scan import scan_files
from skillgen.validate.spec import check_skill_files
from tests.conftest import assert_golden, launch_chromium
from tests.helpers import BENCH, load_bench_page, load_script

check = load_script(BENCH / "check.py")
serve = load_script(BENCH / "serve.py")

SKILL_DIR = BENCH / "skills" / "bench-apply"
CASES = check.load_cases()
AUTOMATED = [case for case in CASES if "fill" in case]


def test_bench_page_model_comes_from_analysis_and_probe(update_golden):
    analysis = json.loads((BENCH / "analysis.json").read_text(encoding="utf-8"))
    probe = probed_page_from_dict(json.loads((BENCH / "probe.json").read_text(encoding="utf-8")))
    result = build_page_model(
        MergeInput(
            route="/apply",
            skill="bench-apply",
            analysis=analysis,
            app_name="Bench",
            app_url="http://localhost:8765",
            probe=probe,
        )
    )
    assert result.questions == ()
    text = json.dumps(page_to_dict(result.page), indent=2, ensure_ascii=False) + "\n"
    assert_golden(BENCH / "page.json", text, update_golden)


def test_bench_skill_is_up_to_date(update_golden):
    files = build_skill_files(load_bench_page(), read_fill_engine())
    for relative, content in files.items():
        assert_golden(SKILL_DIR / relative, content, update_golden)
    on_disk = {p.relative_to(SKILL_DIR).as_posix() for p in SKILL_DIR.rglob("*") if p.is_file()}
    assert on_disk == set(files)


def test_bench_skill_passes_checks():
    files = {
        p.relative_to(SKILL_DIR).as_posix(): p.read_text(encoding="utf-8")
        for p in SKILL_DIR.rglob("*")
        if p.is_file()
    }
    assert check_skill_files(files, "bench-apply") == []
    assert scan_files(files) == []


def test_cases_have_unique_ids_and_known_keys():
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    page = load_bench_page()
    known = {spec.key for spec in page.fields} | {group.id for group in page.groups}
    for case in CASES:
        assert "bench-apply" in case["prompt"]
        for values in (case.get("fill", {}), case.get("fill_follow_up", {})):
            assert set(values) <= known, case["id"]
        assert case["expect"]["outcome"] in ("submitted", "not-submitted")


def test_compare_treats_expected_as_subset():
    assert check.compare({"a": 1, "b": {"c": 2}}, {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}) == []
    assert check.compare({"a": 1}, {"a": 2}) == ["a: expected 1, got 2"]
    assert check.compare({"a": 1}, {}) == ["a: missing"]


@pytest.fixture(scope="module")
def bench_url() -> Iterator[str]:
    server = serve.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        launched = launch_chromium(playwright)
        yield launched
        launched.close()


def _post(url: str) -> None:
    urllib.request.urlopen(urllib.request.Request(url, data=b"", method="POST"), timeout=5).read()


def _check_fill_result(result: dict[str, Any], expected: dict[str, Any]) -> None:
    if "filled_count" in expected:
        assert len(result.get("filled", [])) == expected["filled_count"], result
    if "missing" in expected:
        assert result.get("missing") == expected["missing"], result
    if "ambiguous" in expected:
        assert result.get("ambiguous") == expected["ambiguous"], result
    for key in expected.get("invalid_keys", []):
        assert key in result.get("invalid", {}), result
    for key in expected.get("ambiguous_keys", []):
        assert key in result.get("ambiguous", {}), result
    assert "stale" not in result and "unknown" not in result, result


@pytest.mark.browser
@pytest.mark.parametrize("case", AUTOMATED, ids=[case["id"] for case in AUTOMATED])
def test_fill_script_runs_case_on_bench(case, bench_url, browser):
    _post(f"{bench_url}/api/reset")
    script = (SKILL_DIR / "scripts" / "fill.js").read_text(encoding="utf-8")
    page = browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{bench_url}/apply")
    expect = case["expect"]
    result = json.loads(page.evaluate(script + f"\n__fill({json.dumps(case['fill'])})"))
    _check_fill_result(result, expect.get("fill_result", {}))
    if "submit_result" in expect:
        submitted = json.loads(page.evaluate("__submit()"))
        assert submitted["ok"] is False and submitted["status"] == expect["submit_result"]["status"]
        assert set(expect["submit_result"]["error_keys"]) <= set(submitted["errors"]), submitted
    if case.get("fill_follow_up"):
        follow = json.loads(page.evaluate(f"__fill({json.dumps(case['fill_follow_up'])})"))
        assert not {"missing", "invalid", "ambiguous", "stale"} & set(follow), follow
    submitted = json.loads(page.evaluate("__submit()"))
    assert submitted["ok"] is (expect["outcome"] == "submitted"), submitted
    assert check.check_case(case, bench_url) == []
    assert errors == []
    page.close()


@pytest.mark.browser
def test_fill_script_refuses_wrong_host(bench_url, browser):
    script = (SKILL_DIR / "scripts" / "fill.js").read_text(encoding="utf-8")
    page = browser.new_page()
    page.goto(bench_url.replace("localhost", "127.0.0.1") + "/apply")
    result = json.loads(page.evaluate(script + "\n__fill({full_name: 'Ada Example'})"))
    assert result == {"error": "wrong-host", "expected": "localhost", "actual": "127.0.0.1"}
    assert json.loads(page.evaluate("__submit()"))["error"] == "wrong-host"
    page.close()


@pytest.mark.browser
def test_fill_script_reports_stale_fields(bench_url, browser):
    script = (SKILL_DIR / "scripts" / "fill.js").read_text(encoding="utf-8")
    page = browser.new_page()
    page.goto(f"{bench_url}/apply")
    page.evaluate("document.getElementById('email').remove()")
    result = json.loads(page.evaluate(script + "\n__fill({email: 'a@example.com', nickname: 'x'})"))
    assert result["stale"] == ["email"]
    assert result["unknown"] == ["nickname"]
    page.close()


def test_sample_upload_file_is_synthetic():
    data = Path(BENCH / "files" / "sample-id.pdf").read_bytes()
    assert data.startswith(b"%PDF") and b"synthetic" in data
