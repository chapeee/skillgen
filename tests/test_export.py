import hashlib
import json
import re
import zipfile
from xml.etree import ElementTree

import pytest

from skillgen.assets import read_fill_engine
from skillgen.errors import ExportError
from skillgen.export import (
    BUNDLE_COMPATIBILITY_LEAD,
    CHATGPT_ICON_SVG,
    MANIFEST,
    PLUGIN_AUTHOR,
    build_chatgpt_manifest,
    build_manifest,
    build_plugin_manifest,
    export_chatgpt_plugin,
    export_skills,
    group_skill_files,
)
from skillgen.generate.folder import build_skill_files
from skillgen.workspace import Workspace
from tests.helpers import load_bench_page

# The Agent Plugins 1.0.0 manifest: its top-level keys, author keys and name rule.
PORTABLE_KEYS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
AUTHOR_KEYS = {"name", "email", "url"}
PORTABLE_NAME = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


def make_skills(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_skill_files(
        tmp_path / "skills" / "bench-apply",
        build_skill_files(load_bench_page(), read_fill_engine()),
    )
    (tmp_path / "skills-index.html").write_text("<html></html>")
    return workspace


def test_export_skills_writes_folder_with_manifest(tmp_path):
    workspace = make_skills(tmp_path)
    result = export_skills(workspace, tmp_path / "skills", tmp_path / "out", as_zip=False)
    assert result.skills == ("bench-apply",)
    manifest = (tmp_path / "out" / MANIFEST).read_text()
    skill_md = (tmp_path / "out" / "skills" / "bench-apply" / "SKILL.md").read_bytes()
    assert f"{hashlib.sha256(skill_md).hexdigest()}  skills/bench-apply/SKILL.md" in manifest
    assert (tmp_path / "out" / "skills-index.html").exists()
    assert not any(".skillgen" in str(path) for path in (tmp_path / "out").rglob("*"))


def test_export_skills_writes_plugin_zip(tmp_path):
    workspace = make_skills(tmp_path)
    result = export_skills(
        workspace,
        tmp_path / "skills",
        tmp_path / "dist" / "bench",
        as_zip=True,
        plugin_name="bench",
        app_name="Bench",
    )
    with zipfile.ZipFile(result.path) as bundle:
        names = bundle.namelist()
        plugin = json.loads(bundle.read("bench/.claude-plugin/plugin.json"))
    assert "bench/skills/bench-apply/scripts/fill.js" in names and "bench/MANIFEST.sha256" in names
    assert plugin["name"] == "bench"


def test_export_skills_as_one_skill_writes_the_skill_folder_itself(tmp_path):
    workspace = make_skills(tmp_path)
    result = export_skills(
        workspace,
        tmp_path / "skills",
        tmp_path / "dist" / "acme",
        as_zip=False,
        one_skill_name="acme",
        app_name="Acme",
    )
    out = tmp_path / "dist" / "acme"
    entry = (out / "SKILL.md").read_text(encoding="utf-8")
    assert result.skills == ("bench-apply",)
    assert [p.name for p in out.rglob("SKILL.md")] == ["SKILL.md"]
    assert "name: acme" in entry and BUNDLE_COMPATIBILITY_LEAD in entry
    assert (out / "references" / "bench-apply" / "page.md").is_file()
    assert (out / "scripts" / "bench-apply" / "fill.js").is_file()
    # An upload that takes one skill refuses a plugin manifest and the index page.
    assert not (out / ".claude-plugin").exists() and not (out / "skills-index.html").exists()


def test_export_skills_as_one_skill_zips_under_the_skill_name(tmp_path):
    workspace = make_skills(tmp_path)
    result = export_skills(
        workspace,
        tmp_path / "skills",
        # The destination is named something else on purpose: Claude looks for
        # <skill-name>/SKILL.md inside the archive, whatever the file is called.
        tmp_path / "dist" / "download",
        as_zip=True,
        one_skill_name="acme",
    )
    with zipfile.ZipFile(result.path) as bundle:
        names = bundle.namelist()
    assert result.path.name == "download.zip"
    assert [name for name in names if name.endswith("SKILL.md")] == ["acme/SKILL.md"]
    assert all(name.startswith("acme/") for name in names)


def test_export_skills_as_one_skill_inside_a_plugin_keeps_the_skills_folder(tmp_path):
    workspace = make_skills(tmp_path)
    result = export_skills(
        workspace,
        tmp_path / "skills",
        tmp_path / "dist" / "acme",
        as_zip=True,
        plugin_name="acme",
        one_skill_name="acme",
    )
    with zipfile.ZipFile(result.path) as bundle:
        names = bundle.namelist()
    assert [name for name in names if name.endswith("SKILL.md")] == ["acme/skills/acme/SKILL.md"]
    assert "acme/.claude-plugin/plugin.json" in names


def test_export_skills_refuses_secrets(tmp_path):
    workspace = make_skills(tmp_path)
    path = tmp_path / "skills" / "bench-apply" / "SKILL.md"
    path.write_text(path.read_text() + "\nContact jane.doe@realcompany.io\n")
    with pytest.raises(ExportError, match="email address"):
        export_skills(workspace, tmp_path / "skills", tmp_path / "out", as_zip=False)


def test_export_skills_refuses_invalid_skill(tmp_path):
    workspace = make_skills(tmp_path)
    (tmp_path / "skills" / "bench-apply" / "SKILL.md").write_text("no frontmatter")
    with pytest.raises(ExportError, match="fails its checks"):
        export_skills(workspace, tmp_path / "skills", tmp_path / "out", as_zip=False)


def test_export_skills_needs_skills(tmp_path):
    with pytest.raises(ExportError, match="no skills"):
        export_skills(Workspace(tmp_path), tmp_path / "skills", tmp_path / "out", as_zip=False)


def test_build_manifest_and_plugin_manifest():
    assert build_manifest({"b": "x", "a": "y"}).splitlines()[0].endswith("  a")
    assert json.loads(build_plugin_manifest("p", "", ["s"]))["description"].startswith(
        "Page skills for p"
    )


def test_build_plugin_manifest_names_the_author():
    assert json.loads(build_plugin_manifest("p", "", ["s"]))["author"] == {"name": "chapeee"}


def test_export_chatgpt_plugin_writes_one_skill_with_a_file_per_page(tmp_path):
    workspace = make_skills(tmp_path)
    result = export_chatgpt_plugin(
        workspace, tmp_path / "skills", tmp_path / "out", as_zip=False, plugin_name="bench"
    )
    out = tmp_path / "out"
    skill = out / "skills" / "bench"
    plugin = json.loads((out / "plugin.json").read_text())
    assert result.skills == ("bench-apply",)
    assert plugin["name"] == "bench" and plugin["author"] == {"name": PLUGIN_AUTHOR}
    assert (out / plugin["extensions"]["com.openai"]["interface"]["logo"]).is_file()
    assert [p.name for p in out.rglob("SKILL.md")] == ["SKILL.md"]
    assert (skill / "references" / "bench-apply" / "page.md").is_file()
    assert (skill / "scripts" / "bench-apply" / "fill.js").is_file()
    assert not (out / "skills-index.html").exists() and not (out / ".claude-plugin").exists()
    assert "  plugin.json" in (out / MANIFEST).read_text()


def test_export_chatgpt_plugins_entry_point_sends_the_reader_to_one_page(tmp_path):
    workspace = make_skills(tmp_path)
    export_chatgpt_plugin(
        workspace,
        tmp_path / "skills",
        tmp_path / "out",
        as_zip=False,
        plugin_name="bench",
        app_name="Bench",
    )
    skill = tmp_path / "out" / "skills" / "bench"
    entry = (skill / "SKILL.md").read_text(encoding="utf-8")
    page = (skill / "references" / "bench-apply" / "page.md").read_text(encoding="utf-8")
    fill = (skill / "references" / "bench-apply" / "fill.md").read_text(encoding="utf-8")
    assert "name: bench" in entry and 'compatibility: "Built for ChatGPT' in entry
    assert "`references/bench-apply/page.md`" in entry
    # Each page's own text must point at the files as the bundle lays them out.
    assert "`references/bench-apply/fill.md`" in page
    assert "`scripts/bench-apply/fill.js`" in fill and "`scripts/fill.js`" not in fill
    assert page.startswith("# Bench application — /apply")


def test_export_chatgpt_plugin_leaves_out_developer_test_files(tmp_path):
    workspace = make_skills(tmp_path)
    export_chatgpt_plugin(
        workspace, tmp_path / "skills", tmp_path / "out", as_zip=False, plugin_name="bench"
    )
    written = {p.name for p in (tmp_path / "out").rglob("*") if p.is_file()}
    assert "evals.json" not in written


def test_export_chatgpt_plugin_writes_zip_with_one_root(tmp_path):
    workspace = make_skills(tmp_path)
    result = export_chatgpt_plugin(
        workspace,
        tmp_path / "skills",
        tmp_path / "dist" / "bench",
        as_zip=True,
        plugin_name="bench",
        app_name="Bench",
    )
    with zipfile.ZipFile(result.path) as bundle:
        names = bundle.namelist()
    assert all(name.startswith("bench/") for name in names)
    assert {"bench/plugin.json", "bench/skills/bench/SKILL.md"} <= set(names)
    assert [name for name in names if name.endswith("SKILL.md")] == ["bench/skills/bench/SKILL.md"]


@pytest.mark.parametrize("plugin_name", ["", "Bench", "a" * 70])
def test_export_chatgpt_plugin_refuses_invalid_name(tmp_path, plugin_name):
    workspace = make_skills(tmp_path)
    with pytest.raises(ExportError, match="plugin name"):
        export_chatgpt_plugin(
            workspace, tmp_path / "skills", tmp_path / "out", as_zip=False, plugin_name=plugin_name
        )
    assert not (tmp_path / "out").exists()


def test_export_chatgpt_plugin_refuses_a_name_too_long_for_a_skill_identity(tmp_path):
    workspace = make_skills(tmp_path)
    with pytest.raises(ExportError, match="is longer"):
        export_chatgpt_plugin(
            workspace, tmp_path / "skills", tmp_path / "out", as_zip=False, plugin_name="p" * 40
        )


def test_group_skill_files_keys_by_skill_folder():
    grouped = group_skill_files(
        {
            "skills/one/SKILL.md": "a",
            "skills/one/scripts/fill.js": "b",
            "skills/two/SKILL.md": "c",
            "skills-index.html": "d",
        }
    )
    assert grouped == {
        "one": {"SKILL.md": "a", "scripts/fill.js": "b"},
        "two": {"SKILL.md": "c"},
    }


def test_build_chatgpt_manifest_uses_only_portable_keys():
    plugin = json.loads(build_chatgpt_manifest("acme-forms", "Acme", ["acme-signup"]))
    assert set(plugin) <= PORTABLE_KEYS and set(plugin["author"]) <= AUTHOR_KEYS
    assert PORTABLE_NAME.match(plugin["name"]) and plugin["$schema"].endswith(
        "/1.0.0/plugin.schema.json"
    )
    assert plugin["extensions"]["com.openai"]["interface"]["developerName"] == "chapeee"


def test_build_chatgpt_manifest_keeps_listing_text_short():
    interface = json.loads(build_chatgpt_manifest("x", "A" * 29 + " Long App Name", ["s"]))[
        "extensions"
    ]["com.openai"]["interface"]
    assert interface["displayName"] == "A" * 29
    assert len(interface["shortDescription"]) <= 30


def test_chatgpt_icon_svg_is_square_and_large_enough():
    root = ElementTree.fromstring(CHATGPT_ICON_SVG)
    _, _, width, height = (float(part) for part in root.attrib["viewBox"].split())
    assert width == height >= 48
    assert root.attrib["width"] == root.attrib["height"]
