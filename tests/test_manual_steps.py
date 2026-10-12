from skillgen.generate.manual_steps import (
    build_manual_steps,
    describe_manual_action,
    describe_manual_field,
    render_manual_steps,
)
from skillgen.model.page import Condition, Operator, Strategy, ValueType
from tests.helpers import load_bench_page, load_wizard_page, make_field, make_page


def test_describe_manual_action_says_what_a_person_does():
    assert describe_manual_action(make_field("name")) == "type it (text)"
    assert describe_manual_action(make_field("ok", value_type=ValueType.BOOLEAN)) == (
        "tick it for yes, leave it clear for no"
    )
    plan = make_field("plan", value_type=ValueType.ENUM, options=("Basic", "Pro"))
    assert describe_manual_action(plan) == "choose one (Basic · Pro)"
    upload = make_field("scan", strategy=Strategy.FILE, value_type=ValueType.FILE)
    assert describe_manual_action(upload).startswith("upload the file the user gives")


def test_describe_manual_field_says_when_it_is_needed_and_shown():
    page = make_page(
        [
            make_field("kind", label="Kind"),
            make_field(
                "detail",
                label="Detail",
                required_if=Condition("kind", Operator.IN, ("Other",)),
                visible_if=Condition("kind", Operator.IN, ("Other",)),
            ),
        ]
    )
    assert describe_manual_field(page.fields[1], page) == (
        "Detail: type it (text). Required if Kind is Other. Shown only when Kind is Other."
    )


def test_build_manual_steps_starts_at_the_page_and_ends_at_submit():
    steps = build_manual_steps(load_bench_page())
    assert steps[0] == ["Open http://localhost:8765/apply."]
    assert steps[-1][0].startswith('Check every value, then click "Submit application"')
    assert "only when the user has asked to submit" in steps[-1][0]


def test_build_manual_steps_clicks_into_each_view_before_its_fields():
    heads = [step[0] for step in build_manual_steps(load_wizard_page())]
    assert heads.index('Click "Next" to show Step 2.') < heads.index("**Step 2**")
    assert 'Click "Done".' in heads


def test_render_manual_steps_names_fields_by_label_not_selector():
    page = load_bench_page()
    text = render_manual_steps(page)
    assert all(f"- {spec.label}:" in text for spec in page.fields)
    assert "#full_name" not in text and "## Watch out" in text
