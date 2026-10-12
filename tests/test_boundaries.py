"""Import and output boundaries from CLAUDE.md, checked on the source tree."""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

from skillgen import TOOL_NAME

SOURCE = Path(__file__).resolve().parent.parent / "src" / "skillgen"
MODULES = sorted(SOURCE.rglob("*.py"))
PURE_PACKAGES = ("model", "compile", "generate")
EDGE_IMPORTS = {"subprocess", "socket", "urllib.request", "http", "requests", "shutil"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _relative(path: Path) -> str:
    return path.relative_to(SOURCE).as_posix()


@pytest.mark.parametrize("path", MODULES, ids=_relative)
def test_graphify_is_imported_only_in_graph(path):
    if not _relative(path).startswith("graph/"):
        assert not any(name.split(".")[0] == "graphify" for name in _imports(path))


@pytest.mark.parametrize("path", MODULES, ids=_relative)
def test_playwright_is_imported_only_in_probe(path):
    if not _relative(path).startswith("probe/"):
        assert not any(name.split(".")[0] == "playwright" for name in _imports(path))


@pytest.mark.parametrize("path", MODULES, ids=_relative)
def test_print_is_used_only_in_cli(path):
    if _relative(path) == "cli.py":
        return
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"
    ]
    assert not calls


# Ways a module reads or writes outside itself. Checking only for `open(` let
# `importlib.resources` reads through unnoticed. Each name must stand on its own, so
# `byPath(` inside a generated script is not mistaken for `Path(`.
IO_CALLS = (
    "open",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "Path",
    "getenv",
)
IO_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:" + "|".join(IO_CALLS) + r")\(|resources\.files|os\.environ"
)


@pytest.mark.parametrize("path", MODULES, ids=_relative)
def test_pure_packages_do_no_io(path):
    if _relative(path).split("/")[0] not in PURE_PACKAGES:
        return
    assert not (_imports(path) & EDGE_IMPORTS)
    found = IO_PATTERN.findall(path.read_text(encoding="utf-8"))
    assert found == [], f"{_relative(path)} reaches outside itself: {sorted(set(found))}"


@pytest.mark.parametrize("path", MODULES, ids=_relative)
def test_tool_name_is_not_hard_coded(path):
    if _relative(path) == "__init__.py":
        return
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstring_nodes = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    offending = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstring_nodes
        and TOOL_NAME in node.value
        and not node.value.startswith(f"{TOOL_NAME}.")
    ]
    assert not offending, offending


def test_no_mcp_anywhere_in_source():
    for path in MODULES:
        assert "mcp" not in path.read_text(encoding="utf-8").lower(), path


@pytest.mark.parametrize("path", MODULES, ids=_relative)
def test_every_module_has_tests(path):
    if path.name == "__init__.py":
        return
    tests = Path(__file__).resolve().parent
    package = path.parent.name
    assert (tests / f"test_{path.stem}.py").exists() or (
        tests / f"test_{package}_{path.stem}.py"
    ).exists()


def test_heavy_libraries_are_imported_lazily():
    """`import skillgen.cli` must not pull in the slow optional machinery.

    `jsonschema` and `PyYAML` cost about 0.4s together, which every command paid
    through modules it imported but never used. They are imported where they are
    needed instead; this test keeps them off the startup path.
    """
    code = (
        "import sys, skillgen.cli;"
        "print(','.join(n for n in ('jsonschema', 'yaml') if n in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""
