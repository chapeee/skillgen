from skillgen.assets import read_fill_engine
from skillgen.generate.fill_script import build_fill_script
from skillgen.validate.spec import (
    check_fill_script,
    check_skill_files,
    check_skill_md,
    estimate_tokens,
    find_size_notes,
    split_frontmatter,
)
from tests.helpers import load_bench_page

GOOD = '---\nname: demo-page\ndescription: "Fills the demo form."\n---\n# Demo\n'


def test_check_skill_md_accepts_minimal_valid_file():
    assert check_skill_md(GOOD, "demo-page") == []


def test_check_skill_md_requires_frontmatter():
    assert check_skill_md("# no frontmatter") == [
        "SKILL.md must start with YAML frontmatter between --- lines"
    ]


def test_check_skill_md_rejects_unquoted_description():
    text = GOOD.replace('"Fills the demo form."', "Fills the demo form.")
    assert "description must be quoted in YAML" in check_skill_md(text)


def test_check_skill_md_rejects_bad_name_and_folder_mismatch():
    text = GOOD.replace("demo-page", "Demo--Page")
    problems = check_skill_md(text, "demo-page")
    assert any("lowercase" in problem for problem in problems)
    assert any("differs from its folder" in problem for problem in problems)


def test_check_skill_md_rejects_long_description():
    text = GOOD.replace("Fills the demo form.", "x" * 400)
    assert any("characters" in problem for problem in check_skill_md(text))


def test_check_skill_md_rejects_long_body():
    text = GOOD + "line\n" * 600
    assert any("lines" in problem for problem in check_skill_md(text))


def test_check_skill_md_rejects_unknown_keys_and_non_string_metadata():
    text = GOOD.replace("---\n# Demo", "owner: me\nmetadata:\n  version: 2\n---\n# Demo")
    problems = check_skill_md(text)
    assert "frontmatter: unknown key 'owner'" in problems
    assert "metadata value for 'version' must be a string" in problems


def test_check_skill_md_reports_unparseable_yaml():
    assert check_skill_md("---\nname: [oops\n---\n")[0].startswith("frontmatter does not parse")


def test_check_fill_script_detects_hand_edits():
    script = build_fill_script(load_bench_page(), read_fill_engine())
    assert check_fill_script(script) == []
    edited = script.replace("var WAIT = 5000", "var WAIT = 9000")
    assert check_fill_script(edited) == ["fill.js engine was edited by hand; regenerate the skill"]


def test_check_skill_files_requires_skill_md():
    assert check_skill_files({}, "x") == ["SKILL.md: missing"]


def test_split_frontmatter_and_estimate_tokens():
    raw, body = split_frontmatter(GOOD)
    assert raw.startswith("name:")
    assert body == "# Demo\n"
    assert estimate_tokens("abcd" * 10) == 10


def test_find_size_notes_reports_a_long_body_without_failing_it():
    frontmatter = "\n".join(["---", "name: x", 'description: "y"', "---", ""])
    long_body = frontmatter + "word " * 5000
    (note,) = find_size_notes(long_body)
    assert "over the 5000 budget" in note
    assert find_size_notes(frontmatter + "short\n") == []
    assert not [p for p in check_skill_md(long_body, "x") if "tokens" in p]
