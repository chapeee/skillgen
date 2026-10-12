"""Shared pytest options and fixtures."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="rewrite golden files instead of comparing against them",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-golden"))


def assert_golden(path: Path, actual: str, update: bool) -> None:
    """Compare text with a golden file, or rewrite it when updating."""
    if update or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        return
    expected = path.read_text(encoding="utf-8")
    assert actual == expected, f"{path} differs; rerun with --update-golden and review the diff"


def launch_chromium(playwright: Any) -> Any:
    """Launch Chromium, falling back to a preinstalled binary.

    Set SKILLGEN_CHROMIUM to a Chromium executable when Playwright's own download
    does not match the installed Playwright version.
    """
    chromium = playwright.chromium
    executable = os.environ.get("SKILLGEN_CHROMIUM")
    if executable:
        return chromium.launch(executable_path=executable)
    try:
        return chromium.launch()
    except Exception as error:  # noqa: BLE001 - Playwright's Error type lives in the optional extra
        fallback = Path("/opt/pw-browsers/chromium")
        if fallback.exists():
            return chromium.launch(executable_path=str(fallback))
        pytest.skip(f"no Chromium available: {error}")
