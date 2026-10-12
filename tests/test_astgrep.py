import os

import pytest

from skillgen.assets import find_data_folder
from skillgen.routes.astgrep import (
    find_ast_grep,
    find_declared_routes,
    is_in_skipped_folder,
    pack_applies_to_files,
    read_match,
    repository_files,
    shape_component,
)
from skillgen.routes.hintpacks import RouterPack, load_hint_packs
from tests.conftest import FIXTURES

PACK = RouterPack(
    id="t", about="", language="tsx", rule={}, path_capture="PATH", component_capture="C"
)
needs_ast_grep = pytest.mark.skipif(find_ast_grep() is None, reason="ast-grep is not installed")


def match(path, component="Page"):
    return {
        "file": "src/App.tsx",
        "metaVariables": {"single": {"PATH": {"text": path}, "C": {"text": component}}},
    }


def test_read_match_normalizes_route():
    assert read_match(match("'/projects/:id/edit'"), PACK) == (
        "/projects/:id/edit",
        "Page",
        "src/App.tsx",
    )


@pytest.mark.parametrize("path", ["`/x/${id}`", "base + '/x'", "ROUTE_NAME", ""])
def test_read_match_skips_dynamic_paths(path):
    assert read_match(match(path), PACK) is None


def test_find_declared_routes_without_ast_grep(monkeypatch):
    monkeypatch.setattr("skillgen.routes.astgrep.find_ast_grep", lambda: None)
    assert find_declared_routes(FIXTURES / "react-router-spa", [PACK]) == []


def test_find_declared_routes_keeps_inventory_for_every_pack_and_match(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "routes").mkdir()
    (tmp_path / "src" / "App.tsx").write_text("export default 1;")
    (tmp_path / "routes" / "web.php").write_text("<?php")
    typescript = RouterPack(
        id="tsx",
        about="",
        language="tsx",
        rule={},
        path_capture="PATH",
        component_capture="C",
        globs=("**/*.tsx",),
    )
    laravel = RouterPack(
        id="laravel",
        about="",
        language="php",
        rule={},
        path_capture="PATH",
        component_capture="C",
        globs=("routes/**/*.php",),
    )
    calls = []

    def fake_run(_executable, pack, _repository, _excluded=()):
        calls.append(pack.id)
        file_name = "src/App.tsx" if pack.id == "tsx" else "routes/web.php"
        route = "/tsx" if pack.id == "tsx" else "/laravel"
        return [
            {
                "file": file_name,
                "metaVariables": {
                    "single": {"PATH": {"text": f"'{route}'"}, "C": {"text": "Page"}}
                },
            }
        ]

    monkeypatch.setattr("skillgen.routes.astgrep.find_ast_grep", lambda: "ast-grep")
    monkeypatch.setattr("skillgen.routes.astgrep.run_ast_grep", fake_run)
    found = find_declared_routes(tmp_path, [typescript, laravel])

    assert calls == ["tsx", "laravel"]
    assert [candidate.route for candidate in found] == ["/tsx", "/laravel"]


def test_repository_files_prunes_dependencies_secrets_and_symlinks(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "secrets").mkdir()
    (tmp_path / "generated").mkdir()
    (tmp_path / "src" / "main.ts").write_text("export const route = '/ok';")
    (tmp_path / "node_modules" / "pkg" / "routes.ts").write_text("route('/bad')")
    (tmp_path / "secrets" / "routes.ts").write_text("route('/bad')")
    (tmp_path / "generated" / "routes.ts").write_text("route('/bad')")
    outside = tmp_path.parent / "skillgen-route-scan-outside.ts"
    outside.write_text("route('/outside')")
    try:
        (tmp_path / "src" / "linked.ts").symlink_to(outside)
    except (OSError, NotImplementedError):
        linked = False
    else:
        linked = True

    files = repository_files(tmp_path, ["generated"])
    assert files == ("src/main.ts",)
    if linked:
        assert "src/linked.ts" not in files


@pytest.mark.parametrize(
    ("pattern", "files", "expected"),
    [
        ("**/web.php", ("web.php",), True),
        ("*.tsx", ("src/App.tsx",), True),
        ("routes/**/*.php", ("routes/web.php", "routes/admin/web.php"), True),
        ("routes/**/*.php", ("src/web.php",), False),
        ("{routes,config}/**/*.php", ("routes/web.php",), True),
        ("!**/*.php", ("routes/web.php",), True),
    ],
)
def test_pack_applies_to_files_uses_conservative_glob_shortcut(pattern, files, expected):
    pack = RouterPack(
        id="test",
        about="",
        language="php",
        rule={},
        path_capture="PATH",
        globs=(pattern,),
    )
    assert pack_applies_to_files(pack, files) is expected


def test_pack_applies_to_files_reuses_a_file_iterator_for_each_glob():
    pack = RouterPack(
        id="test",
        about="",
        language="tsx",
        rule={},
        path_capture="PATH",
        globs=("*.vue", "*.tsx"),
    )
    files = (file for file in ("src/App.tsx",))
    assert pack_applies_to_files(pack, files)


@needs_ast_grep
def test_find_declared_routes_on_react_fixture_resolves_components():
    packs = load_hint_packs([find_data_folder("hintpacks")]).routers
    files = {"Signup": "src/pages/Signup.tsx"}
    found = find_declared_routes(
        FIXTURES / "react-router-spa", packs, lambda name, _where: files.get(name)
    )
    signup = next(c for c in found if c.route == "/signup")
    assert signup.entry_files == ("src/pages/Signup.tsx",)
    assert signup.source == "router:react-router-jsx"


@needs_ast_grep
def test_find_declared_routes_on_flask_fixture():
    packs = load_hint_packs([find_data_folder("hintpacks")]).routers
    routes = sorted({c.route for c in find_declared_routes(FIXTURES / "flask-jinja", packs)})
    assert routes == ["/", "/feedback", "/permits/:permit_id/renew"]


def test_find_ast_grep_looks_next_to_python(tmp_path, monkeypatch):
    # Windows only runs a file found on PATH when it has an extension such as .exe.
    binary = tmp_path / ("ast-grep.exe" if os.name == "nt" else "ast-grep")
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setattr("sys.executable", str(tmp_path / "python"))
    monkeypatch.setenv("PATH", "/nonexistent")
    found = find_ast_grep()
    assert found is not None
    # Windows file names are case-insensitive and PATHEXT may report ".EXE".
    assert os.path.normcase(found) == os.path.normcase(str(binary))


def test_shape_component_applies_pack_match_and_format():
    rails = RouterPack(
        id="r",
        about="",
        language="ruby",
        rule={},
        path_capture="P",
        component_match="^[\"']?(?P<name>[\\w/]+)#",
        component_format="{pascal}Controller",
    )
    assert shape_component('"registrations#new"', rails) == "RegistrationsController"
    assert shape_component('"admin/user_roles#edit"', rails) == "UserRolesController"
    assert shape_component("plain", rails) == "plain"
    assert shape_component("Page", PACK) == "Page"


def test_is_in_skipped_folder_spots_dependencies_and_build_output():
    assert is_in_skipped_folder("node_modules/vite-plugin-inspect/dist/client/metric.js")
    assert is_in_skipped_folder(r"web\node_modules\lib\index.js")
    assert is_in_skipped_folder(".cache/routes.js")
    assert not is_in_skipped_folder("src/router/index.js")
