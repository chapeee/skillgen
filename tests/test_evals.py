from skillgen.generate.evals import UNKNOWN_OPTION, build_evals
from tests.helpers import load_bench_page, make_field, make_page


def test_build_evals_has_four_cases():
    evals = build_evals(load_bench_page())
    assert evals["skill_name"] == "bench-apply"
    assert [case["id"] for case in evals["evals"]] == [1, 2, 3, 4]


def test_build_evals_missing_case_lists_missing_labels():
    case = build_evals(load_bench_page())["evals"][1]
    assert "Why are you applying?" in case["expectations"][0]


def test_build_evals_bad_value_uses_unknown_option():
    case = build_evals(load_bench_page())["evals"][2]
    assert UNKNOWN_OPTION in case["prompt"]


def test_build_evals_without_choice_fields_still_has_four_cases():
    assert len(build_evals(make_page([make_field("title", is_required=True)]))["evals"]) == 4


def test_build_evals_no_script_case_forbids_the_javascript_call():
    case = build_evals(load_bench_page())["evals"][3]
    assert "cannot run JavaScript" in case["prompt"] and "do not submit" in case["prompt"]
    assert "Does not run the JavaScript call from SKILL.md" in case["expectations"]
