"""End to end on the three example apps, each in a different stack.

Each app is copied to a temporary folder, then the real CLI runs init, routes and
generate with recorded analyses (no Claude, no network). Output is compared with the
golden files in tests/fixtures/<app>/expected/ (refresh with --update-golden).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from skillgen.cli import main
from skillgen.routes.astgrep import find_ast_grep
from skillgen.workspace import WORKSPACE_DIR
from tests.conftest import FIXTURES, assert_golden

APPS: dict[str, dict[str, Any]] = {
    "react-router-spa": {
        "name": "Fixture Shop",
        "routes": ["/about", "/projects/:projectId/edit", "/settings/profile", "/signup"],
        "needs_ast_grep": True,
    },
    "nextjs-app": {
        "name": "Fixture Store",
        "routes": ["/", "/contact", "/orders/:orderId/return", "/register"],
        "needs_ast_grep": False,
    },
    "flask-jinja": {
        "name": "Fixture Council",
        "routes": ["/", "/feedback", "/permits/:permit_id/renew"],
        "needs_ast_grep": True,
    },
}
HAS_AST_GREP = find_ast_grep() is not None


def run_json(capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, dict[str, Any]]:
    code = main([*arguments, "--json"])
    return code, json.loads(capsys.readouterr().out)


def copy_app(name: str, target: Path) -> Path:
    destination = target / name
    shutil.copytree(
        FIXTURES / name, destination, ignore=shutil.ignore_patterns("analyses", "expected")
    )
    return destination


def read_tree(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize("app", sorted(APPS))
def test_fixture_app_routes_are_found(app, tmp_path, capsys):
    if APPS[app]["needs_ast_grep"] and not HAS_AST_GREP:
        pytest.skip("ast-grep is not installed (reinstall skillgendev)")
    root = copy_app(app, tmp_path)
    assert run_json(capsys, "init", "--root", str(root), "--app-name", APPS[app]["name"])[0] == 0
    code, routes = run_json(capsys, "routes", "--all", "--root", str(root))
    assert code == 0
    assert [route["route"] for route in routes["routes"]] == APPS[app]["routes"]


@pytest.mark.parametrize("app", sorted(APPS))
def test_fixture_app_generates_expected_skills(app, tmp_path, capsys, update_golden):
    root = copy_app(app, tmp_path)
    run_json(capsys, "init", "--root", str(root), "--app-name", APPS[app]["name"])
    for route in APPS[app]["routes"]:
        run_json(capsys, "routes", "--root", str(root), "--route", route, "--no-graph")
    code, result = run_json(
        capsys,
        "generate",
        "--all",
        "--root",
        str(root),
        "--analyzer",
        "replay",
        "--replay-dir",
        str(FIXTURES / app / "analyses"),
    )
    assert code == 0, result
    assert result["failed"] == 0 and result["invalid"] == 0
    expected = FIXTURES / app / "expected"
    produced = read_tree(root / "skills")
    for relative, content in produced.items():
        assert_golden(expected / "skills" / relative, content, update_golden)
    assert set(produced) == set(read_tree(expected / "skills"))
    summary = {
        r["route"]: {k: r[k] for k in ("skill", "status", "open_questions")}
        for r in result["results"]
    }
    assert_golden(
        expected / "generate.json",
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        update_golden,
    )


def test_generate_uses_exact_name_for_one_route(tmp_path, capsys):
    root = copy_app("react-router-spa", tmp_path)
    run_json(capsys, "init", "--root", str(root), "--app-name", "Fixture Shop")
    code, result = run_json(
        capsys,
        "generate",
        "--route",
        "/signup",
        "--name",
        "join-us",
        "--root",
        str(root),
        "--analyzer",
        "replay",
        "--replay-dir",
        str(FIXTURES / "react-router-spa" / "analyses"),
        "--no-graph",
    )
    assert code == 0
    assert result["results"][0]["skill"] == "join-us"
    assert (
        (root / "skills" / "join-us" / "SKILL.md")
        .read_text(encoding="utf-8")
        .startswith("---\nname: join-us\n")
    )
    routes = json.loads((root / WORKSPACE_DIR / "routes.json").read_text(encoding="utf-8"))
    assert routes["routes"][0]["name_locked"] is True


def test_generate_all_uses_name_as_prefix(tmp_path, capsys):
    root = copy_app("nextjs-app", tmp_path)
    run_json(capsys, "init", "--root", str(root), "--app-name", "Fixture Store")
    run_json(capsys, "routes", "--all", "--root", str(root), "--no-graph")
    code, result = run_json(
        capsys,
        "generate",
        "--all",
        "--name",
        "acme",
        "--root",
        str(root),
        "--analyzer",
        "replay",
        "--replay-dir",
        str(FIXTURES / "nextjs-app" / "analyses"),
        "--no-graph",
    )
    assert code == 0
    assert sorted(r["skill"] for r in result["results"]) == [
        "acme-contact",
        "acme-home",
        "acme-orders-return",
        "acme-register",
    ]


def test_generate_rejects_invalid_name(tmp_path, capsys):
    root = copy_app("nextjs-app", tmp_path)
    run_json(capsys, "init", "--root", str(root))
    code, result = run_json(
        capsys,
        "generate",
        "--route",
        "/contact",
        "--name",
        "Bad Name!",
        "--root",
        str(root),
        "--analyzer",
        "replay",
        "--replay-dir",
        str(FIXTURES / "nextjs-app" / "analyses"),
    )
    assert code == 2
    assert "lowercase letters" in result["error"]


def test_regenerate_keeps_user_rules_and_answers(tmp_path, capsys):
    root = copy_app("react-router-spa", tmp_path)
    replay = str(FIXTURES / "react-router-spa" / "analyses")
    run_json(capsys, "init", "--root", str(root), "--app-name", "Fixture Shop")
    generate = (
        "generate",
        "--route",
        "/settings/profile",
        "--root",
        str(root),
        "--analyzer",
        "replay",
        "--replay-dir",
        replay,
        "--no-graph",
    )
    run_json(capsys, *generate)
    skill = "fixture-shop-settings-profile"
    code, _ = run_json(
        capsys,
        "add-rule",
        skill,
        "Display name has no emoji.",
        "--check",
        "display_name ^[\\w .-]+$",
        "--root",
        str(root),
    )
    assert code == 0
    _, questions = run_json(capsys, "questions", "--root", str(root))
    rule_question = next(q for q in questions["questions"] if q["subject"].startswith("rule:"))
    run_json(capsys, "answer", rule_question["id"], "yes", "--root", str(root))
    _, again = run_json(capsys, *generate, "--overwrite")
    text = (root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "Display name has no emoji." in text
    assert "it must not contain an email address" in text
    assert again["results"][0]["open_questions"] == 1
    assert '"p":"^[\\\\w .-]+$"' in (root / "skills" / skill / "scripts" / "fill.js").read_text(
        encoding="utf-8"
    )
