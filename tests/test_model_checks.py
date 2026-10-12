from dataclasses import replace

from skillgen.model.page import Condition, Operator, OptionsSource, Rule, Strategy, ValueType
from skillgen.validate.model_checks import check_page_model, find_cycle
from tests.helpers import PROBED, load_bench_page, make_field, make_page


def test_check_page_model_accepts_bench_page():
    assert check_page_model(load_bench_page()) == []


def test_find_cycle_finds_loop():
    assert find_cycle([("a", "b"), ("b", "c"), ("c", "a")]) == ["a", "b", "c", "a"]
    assert find_cycle([("a", "b"), ("b", "c")]) == []


def test_check_page_model_reports_dependency_cycle():
    page = make_page(
        [
            make_field("a", options_from=OptionsSource(depends_on="b")),
            make_field("b", visible_if=Condition("a", Operator.FILLED)),
        ]
    )
    assert any(problem.startswith("dependency cycle") for problem in check_page_model(page))


def test_check_page_model_reports_unknown_references():
    page = make_page(
        [make_field("a", visible_if=Condition("ghost", Operator.FILLED), section="nowhere")],
        rules=(Rule(text="r", provenance=PROBED, field="phantom"),),
    )
    problems = check_page_model(page)
    assert "a: visible_if names unknown field 'ghost'" in problems
    assert "rule 'r' names unknown field 'phantom'" in problems


def test_check_page_model_reports_bad_keys_and_duplicates():
    page = make_page([make_field("Bad Key"), make_field("ok"), make_field("ok")])
    problems = check_page_model(page)
    assert any("snake_case" in problem for problem in problems)
    assert "ok: key appears twice" in problems


def test_check_page_model_requires_submit():
    assert "page has no submit control" in check_page_model(
        make_page([make_field("a")], submit=None)
    )


def test_check_page_model_flags_select_without_choices():
    page = make_page([make_field("a", strategy=Strategy.NATIVE_SELECT, value_type=ValueType.TEXT)])
    assert "a: a select must have an enum or multi-enum type" in check_page_model(page)


def test_check_page_model_flags_non_unique_selector():
    page = load_bench_page()
    problems = check_page_model(page, {"email": 2, "interests": 5})
    assert problems == ["email: selector '#email' matched 2 elements"]


def test_check_page_model_flags_group_key_shape():
    page = load_bench_page()
    fields = tuple(
        replace(f, key="ref_name") if f.key == "references[].name" else f for f in page.fields
    )
    assert any(
        "must look like references[].name" in p
        for p in check_page_model(replace(page, fields=fields))
    )
