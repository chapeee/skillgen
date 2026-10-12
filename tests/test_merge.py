import pytest

from skillgen.compile.merge import (
    MergeInput,
    build_page_model,
    find_open_candidates,
    find_view_candidates,
    is_page_verified,
    is_risky_step,
)
from skillgen.model.facts import Source
from skillgen.model.page import Strategy, ValueType
from skillgen.model.probe import ProbedCondition, ProbedField, ProbedPage
from tests.helpers import load_wizard_analysis

FIELD = {
    "key": "email",
    "label": "Email",
    "type": "email",
    "required": True,
    "strategy": "native-input",
    "selector": "#email",
    "evidence": [{"file": "src/Form.tsx", "line": 3}],
}
ANALYSIS = {"has_form": True, "title": "Join", "fields": [FIELD], "submit": {"selector": "button"}}


def probed(key="email", **changes):
    base = {
        "key": key,
        "label": "Email",
        "selector": f"#{key}",
        "strategy": Strategy.NATIVE_INPUT,
        "value_type": ValueType.EMAIL,
        "is_required": True,
        "is_proven": True,
        "name": key,
    }
    return ProbedField(**(base | changes))


def merge(analysis=ANALYSIS, probe=None, answers=None):
    return build_page_model(
        MergeInput(
            route="/join",
            skill="demo-join",
            analysis=analysis,
            app_name="Demo",
            probe=probe,
            answers=answers or {},
        )
    )


def test_build_page_model_code_only():
    result = merge()
    (spec,) = result.page.fields
    assert spec.provenance.sources == (Source.EXTRACTED,) and spec.provenance.confidence == 0.85
    assert not result.page.is_verified
    assert result.evidence[0].location == "src/Form.tsx:3"


def test_build_page_model_with_probe_is_verified():
    probe = ProbedPage(
        url="u", title="Join", fields=(probed(),), submit_selector="#go", has_empty_submit=True
    )
    result = merge(probe=probe)
    assert result.page.fields[0].provenance.confidence == 0.985
    assert result.page.is_verified
    assert result.page.submit is not None and result.page.submit.selector == "#go"


def test_build_page_model_adds_probe_only_fields_but_not_repeated_rows():
    probe = ProbedPage(
        url="u",
        title="t",
        fields=(probed(), probed("phone", label="Phone"), probed("rows_0_x", is_repeated=True)),
    )
    keys = [f.key for f in merge(probe=probe).page.fields]
    assert keys == ["email", "phone"]


def test_build_page_model_asks_about_field_the_page_lacks():
    probe = ProbedPage(url="u", title="t", fields=(probed("other", label="Other"),))
    result = merge(probe=probe)
    assert "email" not in [f.key for f in result.page.fields]
    assert any(q.subject == "field:email:presence" for q in result.questions)
    answered = merge(probe=probe, answers={"field:email:presence": "yes"})
    assert "email" in [f.key for f in answered.page.fields]


def test_build_page_model_drops_inferred_rules_and_asks():
    analysis = ANALYSIS | {"rules": [{"text": "Use a work email.", "inferred": True}]}
    result = merge(analysis)
    assert result.page.rules == ()
    assert [q.subject for q in result.questions] == ["rule:1"]
    assert merge(analysis, answers={"rule:1": "yes"}).page.rules[0].provenance.confidence == 1.0


def test_build_page_model_keeps_inferred_gotchas_out_but_asks_about_them():
    analysis = ANALYSIS | {
        "gotchas": [{"text": "maybe slow", "inferred": True}, {"text": "Loads late."}]
    }
    result = merge(analysis)
    assert [n.text for n in result.page.gotchas] == ["Loads late."]
    assert [q.subject for q in result.questions] == ["gotcha:1"]


def test_build_page_model_takes_conditions_from_probe():
    analysis = ANALYSIS | {
        "fields": [
            FIELD,
            FIELD
            | {
                "key": "company",
                "label": "Company",
                "type": "text",
                "required": False,
                "selector": "#company",
            },
        ]
    }
    probe = ProbedPage(
        url="u",
        title="t",
        fields=(probed(), probed("company", label="Company", is_visible=False)),
        conditions=(ProbedCondition("email", "x", ("company",)),),
    )
    company = merge(analysis, probe).page.fields[1]
    assert company.visible_if is not None and company.visible_if.field == "email"


def test_build_page_model_route_params_and_analysis_questions():
    analysis = ANALYSIS | {"questions": [{"text": "Which plan is default?"}]}
    result = build_page_model(MergeInput(route="/teams/:teamId/join", skill="s", analysis=analysis))
    assert [p.name for p in result.page.params] == ["teamId"]
    assert result.questions[-1].text == "Which plan is default?"


def test_is_page_verified_needs_probe():
    assert not is_page_verified([], None)


def test_merge_submit_keeps_selector_when_success_is_inferred():
    submit = {
        "selector": "button",
        "label": "Save",
        "success": {"url_matches": "/done"},
        "inferred": True,
    }
    result = merge(ANALYSIS | {"submit": submit})
    assert result.page.submit is not None and result.page.submit.selector == "button"
    assert result.page.submit.success.url_matches == ""
    assert [q.subject for q in result.questions] == ["submit:success"]
    confirmed = merge(ANALYSIS | {"submit": submit}, answers={"submit:success": "yes"})
    assert confirmed.page.submit.success.url_matches == "/done"


def test_merge_submit_drops_regex_success_url():
    submit = {
        "selector": "button",
        "success": {"url_matches": "/items/\\d+$", "text_appears": "Saved"},
    }
    signal = merge(ANALYSIS | {"submit": submit}).page.submit.success
    assert signal.url_matches == "" and signal.text_appears == "Saved"


def with_open(steps, **extra):
    return ANALYSIS | {"open": {"steps": steps, **extra}}


def test_merge_open_steps_trusts_steps_read_in_the_code():
    result = merge(with_open(['button[title="Page settings"]']))
    assert result.page.open_steps == ('button[title="Page settings"]',)
    assert not [q for q in result.questions if q.subject == "open"]


def test_merge_open_steps_asks_about_deduced_steps():
    result = merge(with_open(["text:Settings"], inferred=True))
    assert result.page.open_steps == ()
    (question,) = [q for q in result.questions if q.subject == "open"]
    assert "text:Settings" in question.text


def test_merge_open_steps_never_trusts_a_click_that_changes_data():
    result = merge(with_open(["text:Delete page"]))
    assert result.page.open_steps == ()
    assert [q for q in result.questions if q.subject == "open"]


def test_merge_open_steps_uses_the_developers_yes():
    asked = merge(with_open(["text:Settings"], inferred=True))
    assert any(q.subject == "open" for q in asked.questions)
    result = merge(with_open(["text:Settings"], inferred=True), answers={"open": "yes"})
    assert result.page.open_steps == ("text:Settings",)
    assert not any(q.subject == "open" for q in result.questions)


def test_merge_open_steps_takes_a_corrected_answer():
    answers = {"open": "text:Page settings; text:Hero"}
    result = merge(with_open(["text:Settings"], inferred=True), answers=answers)
    assert result.page.open_steps == ("text:Page settings", "text:Hero")


def test_merge_open_steps_is_empty_when_the_form_shows_on_load():
    assert merge().page.open_steps == ()


@pytest.mark.parametrize(
    ("step", "risky"),
    [
        ("text:Page settings", False),
        ('button[title="Page settings"]', False),
        ("text:Save", True),
        ("button[type=submit]", True),
        ("text:Sign out", True),
    ],
)
def test_is_risky_step(step, risky):
    assert is_risky_step(step) is risky


GUESSED = {"text": "Saving clears every field you leave empty.", "inferred": True}
READ = {"text": "Region loads after Country is chosen."}


def test_merge_gotchas_keeps_advice_read_in_the_code():
    result = merge(ANALYSIS | {"gotchas": [READ]})
    assert [note.text for note in result.page.gotchas] == [READ["text"]]


def test_merge_gotchas_asks_about_deduced_advice_instead_of_dropping_it():
    result = merge(ANALYSIS | {"gotchas": [READ, GUESSED]})
    assert [note.text for note in result.page.gotchas] == [READ["text"]]
    (question,) = [q for q in result.questions if q.subject == "gotcha:2"]
    assert GUESSED["text"] in question.text


def test_merge_gotchas_uses_deduced_advice_once_confirmed():
    result = merge(ANALYSIS | {"gotchas": [GUESSED]}, answers={"gotcha:1": "yes"})
    assert [note.text for note in result.page.gotchas] == [GUESSED["text"]]


def test_find_open_candidates_offers_deduced_steps_but_never_risky_ones():
    deduced = {"open": {"steps": ["text:Page settings"], "inferred": True}}
    assert find_open_candidates(deduced) == ("text:Page settings",)
    assert find_open_candidates({"open": {"steps": ["text:Save"]}}) == ()
    assert find_open_candidates({}) == ()


def wizard(**changes):
    analysis = load_wizard_analysis()
    return analysis | changes


def merge_wizard(analysis, answers=None):
    return build_page_model(
        MergeInput(route="/wizard", skill="bench-wizard", analysis=analysis, answers=answers or {})
    )


def test_merge_views_trusts_views_read_in_the_code():
    result = merge_wizard(wizard())
    assert [view.name for view in result.page.views][:2] == ["Address tab", "Step 2"]
    assert result.page.views[2].leave == ("text:Done",)
    assert not [q for q in result.questions if q.subject == "views"]


def test_merge_views_asks_about_deduced_views():
    analysis = wizard()
    analysis["views"][1]["inferred"] = True
    result = merge_wizard(analysis)
    assert result.page.views == ()
    (question,) = [q for q in result.questions if q.subject == "views"]
    assert "Step 2 (click text:Next)" in question.text
    answered = merge_wizard(analysis, {"views": "yes"})
    assert len(answered.page.views) == 4


def test_find_view_candidates_stops_at_a_click_that_changes_data():
    analysis = wizard()
    analysis["views"][2]["leave"] = ["text:Save contact"]
    views = find_view_candidates(analysis, {field["key"] for field in analysis["fields"]})
    assert [view.name for view in views] == ["Address tab", "Step 2"]


def test_find_view_candidates_keeps_a_field_in_its_first_view_only():
    analysis = wizard()
    analysis["views"][3]["fields"] = ["agree", "city"]
    views = find_view_candidates(analysis, {field["key"] for field in analysis["fields"]})
    assert views[3].keys == ("agree",)
