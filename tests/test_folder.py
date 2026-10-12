import json

from skillgen.assets import read_fill_engine
from skillgen.generate.folder import (
    EVALS_FILE,
    REFERENCES_FILE,
    SCRIPT_FILE,
    SKILL_FILE,
    build_skill_files,
    with_skill_name,
)
from skillgen.generate.layout_reference import LAYOUT_REFERENCE_FILE
from skillgen.generate.locators import LOCATORS_FILE
from skillgen.generate.manual_steps import MANUAL_STEPS_FILE
from skillgen.generate.skill_md import FILL_REFERENCE
from skillgen.validate.spec import check_skill_files
from tests.helpers import load_bench_page, make_field, make_page


def test_build_skill_files_writes_skill_script_and_evals():
    files = build_skill_files(load_bench_page(), read_fill_engine())
    # The bench page was measured, so its skill also carries the layout reference.
    assert set(files) == {
        SKILL_FILE,
        SCRIPT_FILE,
        EVALS_FILE,
        LAYOUT_REFERENCE_FILE,
        FILL_REFERENCE,
        LOCATORS_FILE,
        MANUAL_STEPS_FILE,
    }
    assert json.loads(files[EVALS_FILE])["skill_name"] == "bench-apply"
    assert check_skill_files(files, "bench-apply") == []


def test_build_skill_files_compiles_user_checks_into_script():
    files = build_skill_files(
        load_bench_page(),
        read_fill_engine(),
        user_block="- Name starts with A.  `check: full_name ^A`",
    )
    assert '"p":"^A"' in files[SCRIPT_FILE]


def test_build_skill_files_adds_references_for_big_pages():
    page = make_page([make_field(f"f{i}") for i in range(60)])
    assert REFERENCES_FILE in build_skill_files(page, read_fill_engine())


def test_with_skill_name_renames():
    assert with_skill_name(load_bench_page(), "my-own-name").skill == "my-own-name"


def test_build_skill_files_carries_every_fill_method_without_a_probe():
    files = build_skill_files(make_page([make_field("title")]), read_fill_engine())
    assert {FILL_REFERENCE, LOCATORS_FILE, MANUAL_STEPS_FILE} <= set(files)
    assert LOCATORS_FILE in files[SKILL_FILE] and MANUAL_STEPS_FILE in files[SKILL_FILE]
