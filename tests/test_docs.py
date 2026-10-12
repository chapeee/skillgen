"""Every command and flag is documented for users (README) and maintainers (CONTRIBUTING)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from skillgen import TOOL_NAME
from skillgen.cli import HANDLERS, build_parser

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
CONTRIBUTING = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
COMMON_FLAGS = {"--help", "--json", "--root", "--verbose"}


def _subparsers() -> dict[str, argparse.ArgumentParser]:
    parser = build_parser()
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return dict(action.choices)


def _command_section(text: str) -> str:
    return text.split("## Command reference", 1)[1].split("\n## ", 1)[0]


@pytest.mark.parametrize("command", sorted(HANDLERS))
def test_every_command_is_in_readme_reference(command):
    assert f"`{TOOL_NAME} {command}" in _command_section(README)


@pytest.mark.parametrize("command", sorted(HANDLERS))
def test_every_command_is_in_contributing_table(command):
    table = CONTRIBUTING.split("## Commands: where each one lives", 1)[1].split("\n## ", 1)[0]
    assert f"`{command}`" in table


@pytest.mark.parametrize("command", sorted(HANDLERS))
def test_every_flag_is_in_readme_reference(command):
    section = _command_section(README)
    row = next(
        line for line in section.splitlines() if line.startswith(f"| `{TOOL_NAME} {command}")
    )
    flags = {
        option
        for action in _subparsers()[command]._actions
        for option in action.option_strings
        if option.startswith("--") and option not in COMMON_FLAGS
    }
    missing = sorted(flag for flag in flags if f"`{flag}" not in row)
    assert not missing, f"README command reference for {command} misses {missing}"


def test_install_scripts_are_documented():
    for text in (README, CONTRIBUTING):
        assert "install-local.ps1" in text and "install-local.sh" in text
