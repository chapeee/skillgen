import pytest

from skillgen.config import Settings
from skillgen.errors import WorkspaceError
from skillgen.model.facts import Evidence, Source
from skillgen.model.route import Question, RouteEntry, RouteTable
from skillgen.workspace import (
    Workspace,
    find_workspace_root,
    read_json,
    write_json,
    write_text_atomically,
)
from tests.helpers import load_bench_page


def test_workspace_create_and_read(tmp_path):
    workspace = Workspace(tmp_path)
    assert not workspace.exists()
    workspace.create(Settings(app_name="Acme"))
    assert workspace.read_settings().app_name == "Acme"
    assert (workspace.folder / ".gitignore").read_text() == "secrets/\ncache/\nlogs/\n"
    assert find_workspace_root(tmp_path / "deeper") == tmp_path


def test_workspace_read_settings_without_init(tmp_path):
    with pytest.raises(WorkspaceError, match="init"):
        Workspace(tmp_path).read_settings()


def test_workspace_routes_questions_and_rules(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.create(Settings())
    table = RouteTable((RouteEntry("/a", "x-a", ("f",), ("user",), has_form=True),))
    workspace.write_routes(table)
    assert workspace.read_routes() == table
    questions = [Question("q1", "x-a", "rule:1", "ok?", ("yes", "no"))]
    workspace.write_questions(questions)
    assert workspace.read_questions() == questions
    workspace.global_rules_path.write_text("# Rules\n- Be brief.\nnot a rule\n")
    assert workspace.read_global_rules() == ("Be brief.",)


def test_workspace_page_round_trip_and_evidence(tmp_path):
    workspace = Workspace(tmp_path)
    page = load_bench_page()
    workspace.write_page(page)
    assert workspace.read_page(page.skill) == page
    assert workspace.read_page("missing") is None
    workspace.write_evidence(page.skill, [Evidence("field:a", Source.EXTRACTED, "a.ts:1")])
    assert "a.ts:1" in (workspace.page_folder(page.skill) / "evidence.jsonl").read_text()


def test_workspace_read_page_rejects_invalid(tmp_path):
    workspace = Workspace(tmp_path)
    write_json(workspace.page_folder("x") / "page.json", {"route": "x"})
    with pytest.raises(WorkspaceError):
        workspace.read_page("x")


def test_write_skill_files_removes_stale_generated_files_only(tmp_path):
    workspace = Workspace(tmp_path)
    folder = tmp_path / "skills" / "x"
    workspace.write_skill_files(
        folder, {"SKILL.md": "a", "references/fields.md": "r", "notes.md": "mine"}
    )
    workspace.write_skill_files(folder, {"SKILL.md": "b"})
    assert workspace.read_skill_files(folder) == {"SKILL.md": "b", "notes.md": "mine"}


def test_read_json_reports_problems(tmp_path):
    with pytest.raises(WorkspaceError, match="does not exist"):
        read_json(tmp_path / "x.json")
    (tmp_path / "bad.json").write_text("{")
    with pytest.raises(WorkspaceError, match="not valid JSON"):
        read_json(tmp_path / "bad.json")


def test_write_text_atomically_writes_the_same_bytes_on_every_system(tmp_path):
    target = tmp_path / "SKILL.md"
    write_text_atomically(target, "one\ntwo\n")
    assert target.read_bytes() == b"one\ntwo\n"
