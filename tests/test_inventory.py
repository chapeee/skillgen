"""The in-page inventory: every field and everything clickable, with its own warnings.

A reader uses the clickable list to work out what opens a part of a form that is not on
screen yet. Most of what a page offers to click belongs to its chrome or leads to
another page, and following those collects another page's fields as if they were this
one's, so each is marked rather than left to be guessed at.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

import pytest

from skillgen.generate.fill_script import find_forbidden_syntax
from skillgen.probe.runner import load_extract_script
from tests.conftest import launch_chromium
from tests.helpers import BENCH, load_script

SCRIPT = load_extract_script()

PAGE = """
<nav><a href="/other">Other page</a><button id="menu">Menu</button></nav>
<main>
  <h1>Apply</h1>
  <form>
    <label for="name">Full name</label><input id="name" name="name">
    <button id="more" type="button" aria-expanded="false" aria-controls="extra">More
      details</button>
    <div id="extra" hidden><input id="note" name="note"></div>
    <a href="#section">Jump to section</a>
    <a href="https://example.com/away">Leave</a>
    <button id="wipe" type="button">Reset form</button>
    <button id="go" type="submit">Submit application</button>
  </form>
</main>
"""


def test_extract_script_is_es2019_only():
    assert find_forbidden_syntax(SCRIPT) == []


@pytest.fixture(scope="module")
def browser_page() -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        page = browser.new_page()
        yield page
        browser.close()


def inventory(page: Any) -> dict[str, Any]:
    """Run the script and return its result, with clickables keyed by label."""
    out: dict[str, Any] = page.evaluate(SCRIPT)
    out["by_label"] = {item["label"]: item for item in out["clickables"]}
    return out


@pytest.mark.browser
def test_inventory_lists_clickables_with_a_step_that_can_be_replayed(browser_page):
    browser_page.set_content(PAGE)
    found = inventory(browser_page)["by_label"]
    assert {"Menu", "More details", "Reset form", "Submit application"} <= set(found)
    # A selector when it names one element, else the label: the two forms an open step
    # may take, so what the inventory reports can be replayed as it stands.
    assert found["More details"]["step"] == "#more"
    assert found["Jump to section"]["step"] == "text:Jump to section"


@pytest.mark.browser
def test_inventory_marks_the_pages_own_chrome(browser_page):
    browser_page.set_content(PAGE)
    found = inventory(browser_page)["by_label"]
    assert found["Menu"]["chrome"] is True
    assert found["Other page"]["chrome"] is True
    assert found["More details"]["chrome"] is False


@pytest.mark.browser
def test_inventory_marks_a_click_that_would_leave_the_page(browser_page):
    browser_page.set_content(PAGE)
    found = inventory(browser_page)["by_label"]
    assert found["Other page"]["leaves"] is True
    assert found["Leave"]["leaves"] is True
    # An anchor stays on the page, so it is not a way off it.
    assert found["Jump to section"]["leaves"] is False
    assert found["More details"]["leaves"] is False


@pytest.mark.browser
def test_inventory_marks_a_click_that_would_destroy_work(browser_page):
    """Discovery clicks what the inventory offers, so anything costly must be named."""
    browser_page.set_content(PAGE)
    found = inventory(browser_page)["by_label"]
    assert found["Reset form"]["risky"] is True
    assert found["Submit application"]["risky"] is True
    assert found["More details"]["risky"] is False


@pytest.mark.browser
def test_inventory_reports_what_a_control_expands(browser_page):
    browser_page.set_content(PAGE)
    found = inventory(browser_page)["by_label"]["More details"]
    assert found["collapsed"] is True and found["opens"] == "extra"


@pytest.mark.browser
def test_inventory_still_reports_the_fields_it_always_did(browser_page):
    """The clickable list is added beside the field list, never in place of it."""
    browser_page.set_content(PAGE)
    out = inventory(browser_page)
    assert [control["name"] for control in out["controls"]] == ["name", "note"]
    assert out["title"] == "Apply"
    assert out["submit"]["label"] == "Submit application"


@pytest.fixture(scope="module")
def wizard(browser_page) -> Any:
    serve = load_script(BENCH / "serve.py")
    server = serve.make_server("127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    browser_page.goto(f"http://localhost:{server.server_address[1]}/wizard")
    yield browser_page
    server.shutdown()


@pytest.mark.browser
def test_inventory_finds_what_opens_each_part_of_a_real_wizard(wizard):
    found = inventory(wizard)["by_label"]
    # The tabs and the step button are how the parts behind clicks are reached.
    for label, role in (("Personal", "tab"), ("Address", "tab"), ("Next", "button")):
        assert found[label]["role"] == role
        assert found[label]["risky"] is False and found[label]["chrome"] is False
    assert found["Send"]["risky"] is True
