from skillgen.generate.locators import (
    describe_field_action,
    describe_field_timing,
    describe_locator_clicks,
    find_field_role,
    render_locators,
    split_by_view,
)
from skillgen.model.page import Condition, Operator, Strategy, ValueType
from tests.helpers import load_bench_page, load_wizard_page, make_field, make_page


def test_find_field_role_follows_the_control():
    assert find_field_role(make_field("name")) == "textbox"
    assert find_field_role(make_field("age", value_type=ValueType.NUMBER)) == "spinbutton"
    assert find_field_role(make_field("ok", value_type=ValueType.BOOLEAN)) == "checkbox"
    assert find_field_role(make_field("day", value_type=ValueType.DATE)) == ""
    assert find_field_role(make_field("kind", strategy=Strategy.NATIVE_SELECT)) == "combobox"


def test_find_field_role_gives_choice_fields_the_role_of_each_option():
    single = make_field("plan", strategy=Strategy.CHOICE, value_type=ValueType.ENUM)
    many = make_field("tags", strategy=Strategy.CHOICE, value_type=ValueType.MULTI_ENUM)
    assert (find_field_role(single), find_field_role(many)) == ("radio", "checkbox")


def test_describe_field_action_uses_playwright_verbs():
    select = make_field("kind", strategy=Strategy.NATIVE_SELECT, value_type=ValueType.ENUM)
    upload = make_field("scan", strategy=Strategy.FILE, value_type=ValueType.FILE)
    assert describe_field_action(make_field("name")) == "`fill(value)`"
    assert describe_field_action(select) == "`selectOption({ label: value })`"
    assert "setInputFiles()" in describe_field_action(upload)


def test_describe_field_timing_names_conditions_and_loads():
    page = make_page(
        [
            make_field("kind", label="Kind"),
            make_field(
                "detail",
                visible_if=Condition("kind", Operator.IN, ("Other",)),
            ),
        ]
    )
    assert describe_field_timing(page.fields[1], page) == "only when Kind is Other"
    assert describe_field_timing(page.fields[0], page) == ""


def test_describe_locator_clicks_writes_text_and_css_steps():
    assert describe_locator_clicks(("text:Next", "#done")) == (
        '`getByText("Next")`, then `locator("#done")`'
    )


def test_split_by_view_keeps_fill_order_and_groups_each_part():
    page = load_wizard_page()
    runs = split_by_view(page)
    assert [spec.key for _, fields in runs for spec in fields] == [s.key for s in page.fields]
    assert [view.name if view else "" for view, _ in runs] == [
        "",
        *(view.name for view in page.views),
    ]


def test_render_locators_lists_every_field_once():
    page = load_bench_page()
    text = render_locators(page)
    for spec in page.fields:
        assert text.count(f"| `{spec.key}` |") == 1
    assert "`#add-reference`" in text and '"Submit application"' in text


def test_render_locators_shows_how_to_reach_each_view():
    text = render_locators(load_wizard_page())
    assert '## Step 2\nShow it with `getByText("Next")`.' in text
    assert "## On the form" in text


def test_render_locators_is_data_not_code():
    text = render_locators(load_bench_page())
    assert "```" not in text and "require(" not in text and "import " not in text
