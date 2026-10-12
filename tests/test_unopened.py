"""What the live page offered that the code reading never accounted for.

A page's fields and the parts behind a click come from the code; the browser replays
what that reading found. Anything it missed is never opened and never reaches the skill,
so the inventory is compared against the model and the difference is reported.
"""

from __future__ import annotations

from dataclasses import replace

from skillgen.compile.unopened import (
    MissedOnPage,
    describe_missed,
    find_missed_on_page,
    looks_like_an_opener,
)
from skillgen.model.page import View
from skillgen.model.probe import ProbedPage
from tests.helpers import make_field, make_page


def clickable(label: str, **changes: object) -> dict[str, object]:
    """One inventory entry, worth opening unless a change says otherwise."""
    return {
        "label": label,
        "step": f"text:{label}",
        "role": "summary",
        "visible": True,
        "collapsed": True,
        "opens": "",
        "chrome": False,
        "leaves": False,
        "risky": False,
        "disabled": False,
        **changes,
    }


def probed(fields: tuple[str, ...] = (), clickables: tuple[dict[str, object], ...] = ()):
    """A capture holding only what these tests care about."""
    specs = tuple(replace(make_field(key), label=key) for key in fields)
    page = ProbedPage(url="http://localhost/x", title="x", fields=(), clickables=clickables)
    return replace(page, fields=tuple(_as_probed(spec) for spec in specs))


def _as_probed(spec: object):
    from skillgen.model.probe import ProbedField  # noqa: PLC0415 - test-local

    return ProbedField(
        key=spec.key,  # type: ignore[attr-defined]
        label=spec.label,  # type: ignore[attr-defined]
        selector=spec.selector,  # type: ignore[attr-defined]
        strategy=spec.strategy,  # type: ignore[attr-defined]
        value_type=spec.value_type,  # type: ignore[attr-defined]
    )


def test_a_collapsed_panel_is_worth_opening():
    assert looks_like_an_opener(clickable("Witnesses")) is True


def test_a_control_that_holds_nothing_back_is_not_worth_opening():
    plain = clickable("Help", role="button", collapsed=False, opens="")
    assert looks_like_an_opener(plain) is False


def test_a_tab_and_a_control_that_names_what_it_opens_are_both_worth_opening():
    assert looks_like_an_opener(clickable("Address", role="tab", collapsed=False)) is True
    assert looks_like_an_opener(clickable("More", role="button", opens="extra")) is True


def test_the_pages_own_chrome_a_link_away_and_a_costly_click_are_all_refused():
    """Clicking these either opens nothing of the form or costs too much."""
    for flag in ("chrome", "leaves", "risky", "disabled"):
        assert looks_like_an_opener(clickable("Menu", **{flag: True})) is False
    assert looks_like_an_opener(clickable("Hidden", visible=False)) is False


def test_a_field_on_the_page_that_the_model_lacks_is_reported():
    page = make_page([make_field("full_name")])
    missed = find_missed_on_page(page, probed(fields=("full_name", "witness_name")))
    assert missed.fields == ("witness_name",)
    assert "the live page shows 1 field(s)" in describe_missed(missed)[0]


def test_a_panel_the_run_never_opened_is_reported_with_the_flag_to_use():
    page = make_page([make_field("a")])
    missed = find_missed_on_page(page, probed(clickables=(clickable("Witnesses"),)))
    assert missed.unopened == (("Witnesses", "text:Witnesses"),)
    assert "--open text:Witnesses" in describe_missed(missed)[0]


def test_a_panel_the_code_already_opens_is_not_reported():
    """A view's own clicks, and the developer's `--open`, are already accounted for."""
    opened = make_page(
        [make_field("a")], views=(View(name="Witnesses", enter=("text:Witnesses",), keys=("a",)),)
    )
    found = find_missed_on_page(opened, probed(clickables=(clickable("Witnesses"),)))
    assert found.unopened == ()
    by_flag = replace(make_page([make_field("a")]), open_steps=("text:Witnesses",))
    assert find_missed_on_page(by_flag, probed(clickables=(clickable("Witnesses"),))).unopened == ()


def test_a_step_the_run_made_itself_is_not_reported():
    page = make_page([make_field("a")])
    probe = probed(clickables=(clickable("Witnesses"),))
    assert find_missed_on_page(page, probe, steps_used=("text:Witnesses",)).unopened == ()


def test_nothing_is_reported_when_the_code_accounted_for_the_whole_page():
    page = make_page([make_field("full_name")])
    missed = find_missed_on_page(page, probed(fields=("full_name",)))
    assert missed.is_empty and describe_missed(missed) == []
    assert MissedOnPage().is_empty is True


def test_the_report_is_bounded_so_one_page_cannot_fill_a_runs_output():
    page = make_page([make_field("a")])
    many = tuple(clickable(f"Panel {n}") for n in range(30))
    missed = find_missed_on_page(
        page, probed(fields=tuple(f"k{n}" for n in range(30)), clickables=many)
    )
    assert len(missed.fields) == 8 and len(missed.unopened) == 8
