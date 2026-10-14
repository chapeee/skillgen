"""Read a URL's controls and geometry without interacting with its forms."""

from __future__ import annotations

from typing import Any

from skillgen.config import check_app_url
from skillgen.errors import ProbeError
from skillgen.model.probe import ProbedPage
from skillgen.model.serialize import viewport_from_list
from skillgen.probe.classify import build_probed_fields
from skillgen.probe.runner import (
    CAPTURE_VIEWPORT,
    _require_playwright,
    launch_chromium,
    read_controls,
    settle,
)


def _guard_request(route: Any) -> None:
    """Allow reads only; Any is Playwright's optional route object."""
    if route.request.method in ("GET", "HEAD", "OPTIONS"):
        route.continue_()
    else:
        route.abort()


def read_url(url: str) -> ProbedPage:
    """Open a URL in fresh Chromium and read the existing extraction script once.

    Args:
        url: An absolute HTTP(S) page URL.

    Returns:
        Observed controls and x/y; no fill or submission is marked proven.

    Raises:
        ProbeError: If the page cannot be loaded.
        ProbeUnavailableError: If Playwright is not installed.
    """
    check_app_url(url)
    sync_api = _require_playwright()
    with sync_api.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        try:
            context = browser.new_context(viewport=CAPTURE_VIEWPORT, service_workers="block")
            context.route("**/*", _guard_request)
            page = context.new_page()
            response = page.goto(url)
            if response is not None and response.status >= 400:
                raise ProbeError(f"could not open {url}: HTTP {response.status}")
            settle(page)
            found = read_controls(page)
            width, height = viewport_from_list(found.get("viewport"))
            submit = found.get("submit") or {}
            return ProbedPage(
                url=page.url,
                title=str(found.get("title", "")),
                fields=tuple(build_probed_fields(found.get("controls", []))),
                submit_selector=str(submit.get("selector", "")),
                submit_label=str(submit.get("label", "")),
                viewport_width=width,
                viewport_height=height,
            )
        except sync_api.Error as error:
            raise ProbeError(f"could not read {url}: {str(error).splitlines()[0]}") from error
        finally:
            browser.close()
