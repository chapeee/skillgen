from dataclasses import replace

from skillgen.drift.diff import diff_pages
from skillgen.model.page import OptionsSource, SubmitSpec, SuccessSignal, ValueType
from tests.helpers import make_field, make_page


def kinds(old, new):
    return [(c.kind, c.subject) for c in diff_pages(old, new)]


def test_diff_pages_reports_field_changes():
    old = make_page([make_field("a"), make_field("b", options=("x", "y"))])
    new = make_page(
        [
            make_field("a", label="A2", is_required=True, value_type=ValueType.EMAIL),
            make_field("b", options=("x", "z")),
            make_field("c"),
        ]
    )
    assert kinds(old, new) == [
        ("label-changed", "a"),
        ("type-changed", "a"),
        ("required-changed", "a"),
        ("options-changed", "b"),
        ("field-added", "c"),
    ]
    options = next(c for c in diff_pages(old, new) if c.kind == "options-changed")
    assert options.detail == "added z; removed y"


def test_diff_pages_reports_removals_and_dependencies():
    old = make_page([make_field("a"), make_field("b")])
    new = make_page([make_field("b", options_from=OptionsSource(depends_on="a"))])
    assert kinds(old, new) == [("field-removed", "a"), ("dependency-added", "b")]


def test_diff_pages_reports_submit_changes():
    old = make_page([make_field("a")])
    new = replace(
        old,
        submit=SubmitSpec(selector="#go", label="Go", success=SuccessSignal(url_matches="/done")),
    )
    assert kinds(old, new) == [("submit-changed", "submit"), ("success-changed", "submit")]
    assert kinds(old, replace(old, submit=None)) == [("submit-changed", "submit")]


def test_diff_pages_is_empty_for_same_page():
    page = make_page([make_field("a")])
    assert diff_pages(page, page) == []
