"""The read-only browser pass exposes only navigation, waiting, and extraction."""

from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from skillgen.errors import ProbeError
from skillgen.probe import readonly
from skillgen.probe.runner import load_extract_script


@pytest.fixture
def browser(monkeypatch):
    page = Mock(spec=["goto", "wait_for_timeout", "wait_for_load_state", "evaluate", "url"])
    page.url = "https://example.com/final"
    page.goto.return_value.status = 200
    page.evaluate.return_value = {"title": "Demo", "controls": [], "viewport": [1280, 900]}
    context = Mock(spec=["route", "new_page"])
    context.new_page.return_value = page
    browser = Mock(spec=["new_context", "close"])
    browser.new_context.return_value = context

    @contextmanager
    def start():
        yield object()

    api = Mock()
    api.sync_playwright = start
    api.Error = RuntimeError
    monkeypatch.setattr(readonly, "_require_playwright", lambda: api)
    monkeypatch.setattr(readonly, "launch_chromium", lambda _: browser)
    return browser, context, page


def test_read_url_uses_extract_once_without_interaction(browser):
    instance, context, page = browser
    capture = readonly.read_url("https://example.com/start")
    page.goto.assert_called_once_with("https://example.com/start")
    page.evaluate.assert_called_once_with(load_extract_script())
    assert capture.url == page.url and not capture.has_empty_submit
    assert instance.new_context.call_args.kwargs["service_workers"] == "block"
    context.route.assert_called_once_with("**/*", readonly._guard_request)
    instance.close.assert_called_once()


@pytest.mark.parametrize("is_http_error", [False, True])
def test_read_url_closes_browser_on_navigation_failure(browser, is_http_error):
    instance, _, page = browser
    if is_http_error:
        page.goto.return_value.status = 503
    else:
        page.goto.side_effect = RuntimeError("navigation timed out")
    with pytest.raises(ProbeError):
        readonly.read_url("https://example.com/failure")
    page.evaluate.assert_not_called()
    instance.close.assert_called_once()
