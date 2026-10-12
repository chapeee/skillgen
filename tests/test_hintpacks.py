import json
import shutil

import pytest

from skillgen.assets import find_data_folder
from skillgen.cli import main
from skillgen.errors import HintPackError
from skillgen.routes.astgrep import find_ast_grep
from skillgen.routes.hintpacks import load_hint_packs, parse_folder_pack, parse_router_pack
from tests.conftest import FIXTURES


def test_load_hint_packs_reads_shipped_packs():
    packs = load_hint_packs([find_data_folder("hintpacks")])
    assert {p.id for p in packs.folders} >= {
        "nextjs-app",
        "nextjs-pages",
        "nuxt-pages",
        "sveltekit-routes",
    }
    assert {p.id for p in packs.routers} >= {
        "react-router-jsx",
        "route-objects",
        "express",
        "flask",
        "django",
    }


def test_load_hint_packs_later_folder_overrides(tmp_path):
    (tmp_path / "x.yml").write_text(
        "id: express\nkind: router\nlanguage: js\nrule: {pattern: x}\ncaptures: {path: P}\n"
    )
    packs = load_hint_packs([find_data_folder("hintpacks"), tmp_path])
    express = next(p for p in packs.routers if p.id == "express")
    assert express.language == "js"


def test_load_hint_packs_skips_missing_folder(tmp_path):
    assert load_hint_packs([tmp_path / "nope"]).routers == ()


def test_parse_folder_pack_requires_fields():
    with pytest.raises(HintPackError):
        parse_folder_pack({"id": "x"})


def test_parse_folder_pack_rejects_bad_regex():
    with pytest.raises(HintPackError, match="regular expression"):
        parse_folder_pack({"id": "x", "roots": ["a"], "page_files": ["*.x"], "params": ["("]})


def test_parse_router_pack_requires_path_capture():
    with pytest.raises(HintPackError, match=r"captures\.path"):
        parse_router_pack({"id": "x", "language": "ts", "rule": {"pattern": "a"}, "captures": {}})


def test_load_hint_packs_rejects_non_mapping(tmp_path):
    (tmp_path / "bad.yml").write_text("- a\n- b\n")
    with pytest.raises(HintPackError, match="mapping"):
        load_hint_packs([tmp_path])


STACKS = {
    "rails": [("/signup", ["app/controllers/registrations_controller.rb"])],
    "spring": [("/signup", ["src/main/java/app/SignupController.java"])],
    "aspnet": [
        ("/contact", ["Pages/Contact.cshtml"]),
        ("/signup", ["Controllers/SignupController.cs"]),
    ],
    "phoenix": [
        ("/contact", ["lib/app_web/live/contact_live.ex"]),
        ("/signup", ["lib/app_web/controllers/signup_controller.ex"]),
    ],
    "laravel": [("/developer/kyc", ["app/Http/Controllers/KycController.php"])],
    "vue-router-js": [("/signup", ["src/views/SignupView.vue"])],
}


@pytest.mark.skipif(find_ast_grep() is None, reason="ast-grep is not installed")
@pytest.mark.parametrize("stack", sorted(STACKS))
def test_hint_packs_find_routes_in_each_stack(stack, tmp_path, capsys):
    root = tmp_path / stack
    shutil.copytree(FIXTURES / "hintpacks" / stack, root)
    main(["init", "--root", str(root), "--json"])
    capsys.readouterr()
    assert main(["routes", "--all", "--no-claude", "--root", str(root), "--json"]) == 0
    routes = json.loads(capsys.readouterr().out)["routes"]
    assert [(r["route"], r["entry_files"]) for r in routes] == STACKS[stack]


@pytest.mark.skipif(find_ast_grep() is None, reason="ast-grep is not installed")
def test_hint_packs_never_read_routes_from_dependencies(tmp_path, capsys):
    root = tmp_path / "app"
    shutil.copytree(FIXTURES / "hintpacks" / "vue-router-js", root)
    # Bundled code in dependencies looks like route declarations; it must be skipped.
    bundle = root / "node_modules" / "some-plugin" / "dist" / "client.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(
        "\n".join(["app.get('/color', handler);", "const r = { path: '/dataMax', component: X };"])
    )
    main(["init", "--root", str(root), "--json"])
    capsys.readouterr()
    assert main(["routes", "--all", "--no-claude", "--root", str(root), "--json"]) == 0
    routes = json.loads(capsys.readouterr().out)["routes"]
    assert [r["route"] for r in routes] == ["/signup"]
