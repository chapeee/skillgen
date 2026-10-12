from dataclasses import replace

import yaml

from skillgen.generate.skill_md import (
    MAX_INLINE_FIELDS,
    SkillText,
    build_page_description,
    describe_accepts,
    describe_condition,
    render_browser_actions,
    render_fill_reference,
    render_references,
    render_skill_md,
    split_fields,
)
from skillgen.generate.user_rules import USER_END, USER_START, extract_user_block
from skillgen.model.page import (
    Box,
    Condition,
    Layout,
    Limits,
    Operator,
    RouteParam,
    Strategy,
    ValueType,
)
from skillgen.validate.spec import check_skill_md, split_frontmatter
from tests.helpers import load_bench_page, load_wizard_page, make_field, make_page


def test_render_skill_md_passes_spec_checks():
    page = load_bench_page()
    assert check_skill_md(render_skill_md(page), page.skill) == []


def test_render_skill_md_quotes_metadata_as_strings():
    raw, _ = split_frontmatter(render_skill_md(replace(load_bench_page(), is_verified=True)))
    data = yaml.safe_load(raw)
    assert data["metadata"]["verified"] == "true"
    assert all(isinstance(value, str) for value in data["metadata"].values())


def test_render_skill_md_keeps_user_block():
    text = render_skill_md(load_bench_page(), SkillText(user_block="- Never on Sundays."))
    assert f"{USER_START}\n- Never on Sundays.\n{USER_END}" in text
    assert extract_user_block(text) == "- Never on Sundays."


def test_render_skill_md_copies_global_rules():
    text = render_skill_md(load_bench_page(), SkillText(global_rules=("Use British spelling.",)))
    assert "### Rules for all pages\n- Use British spelling." in text


def test_render_skill_md_lists_every_field_in_fill_order():
    page = load_bench_page()
    text = render_skill_md(page)
    positions = [text.index(f"| `{spec.key}` |") for spec in page.fields]
    assert positions == sorted(positions)


def test_render_skill_md_has_no_evidence():
    text = render_skill_md(load_bench_page())
    for word in ("RUNTIME_PROBED", "EXTRACTED", "confidence", "page.json"):
        assert word not in text


def test_render_skill_md_asks_for_route_params():
    page = make_page(
        [make_field("title")], route="/things/:id/edit", params=(RouteParam("id", "thing id"),)
    )
    assert "The route needs `id` (thing id)" in render_skill_md(page)


def test_render_skill_md_mentions_mcp_nowhere():
    assert "MCP" not in render_skill_md(load_bench_page())


def test_render_skill_md_sends_the_reader_to_the_fill_call_first():
    text = render_skill_md(load_bench_page())
    how = text.split("## How to fill", 1)[1].split("\n## ", 1)[0]
    assert how.index("references/fill.md") < how.index("references/locators.md")
    assert how.index("references/locators.md") < how.index("references/manual-steps.md")
    assert "do not take a screenshot or read the page first" in how


def test_render_skill_md_does_not_carry_the_fill_call_itself():
    text = render_skill_md(load_bench_page())
    assert "```js" not in text and "__skillgen" not in text


def test_render_skill_md_puts_what_a_fill_needs_before_what_explains_it():
    # An agent may keep only the start of a skill after a conversation is compacted.
    text = render_skill_md(load_bench_page())
    order = ["## How to fill", "## Fields", "## Rules", "## Gotchas", "## Submit and verify"]
    assert [text.index(part) for part in order] == sorted(text.index(p) for p in order)


def test_render_fill_reference_carries_the_call_and_how_to_read_it():
    page = load_bench_page()
    text = render_fill_reference(page)
    assert text.startswith(f"# {page.title} — the fill call")
    assert "```js" in text and "await (async function" in text
    assert "`escalate`" in text and "`rejected`" in text


def test_render_skill_md_warns_that_direct_writes_can_fail():
    text = render_skill_md(load_bench_page())
    for words in ("sandboxed browser", "protected page", "framework-controlled form"):
        assert words in text


def test_render_skill_md_names_abilities_not_one_products_tools():
    text = render_skill_md(load_bench_page())
    for tool in ("javascript_tool", "form_input", "computer use", "Playwright"):
        assert tool not in text


def test_render_browser_actions_lists_only_the_kinds_the_page_has():
    lines = render_browser_actions(make_page([make_field("title")]))
    assert "- Text, dates and numbers: click the field, type the value." in lines
    assert not any(line.startswith("- A file") for line in lines)


def test_describe_condition_uses_labels():
    page = make_page([make_field("kind"), make_field("code")])
    condition = Condition("kind", Operator.IN, ("A", "B"))
    assert describe_condition(condition, page) == "Kind is A or B"
    assert describe_condition(Condition("kind", Operator.CHECKED), page) == "Kind is ticked"


def test_describe_accepts_shows_lengths_and_options():
    assert (
        describe_accepts(make_field("n", limits=Limits(min_length=3, max_length=80)))
        == "text, 3–80 chars"
    )
    many = make_field("c", value_type=ValueType.ENUM, options=tuple(f"o{i}" for i in range(12)))
    assert describe_accepts(many).endswith("(12 in all)")


def test_split_fields_moves_optional_fields_to_references():
    fields = [make_field(f"f{i}", is_required=i < 5) for i in range(MAX_INLINE_FIELDS + 20)]
    page = make_page(fields)
    inline, extra = split_fields(page)
    assert len(inline) == MAX_INLINE_FIELDS
    assert all(spec.is_required for spec in fields[:5] if spec in inline)
    assert len(extra) == 20
    references = render_references(page)
    assert "| `f59` |" in references
    text = render_skill_md(page, SkillText(has_references=True))
    assert "references/fields.md" in text and "| `f59` |" not in text


def test_build_page_description_fits_limit():
    page = load_bench_page()
    description = build_page_description(page)
    assert len(description) < 300
    assert description.startswith("Fills the Bench application form at /apply in Bench")


def stacked_layout(*keys: str) -> Layout:
    boxes = tuple((key, Box(100, 100 + index * 80, 300, 40)) for index, key in enumerate(keys))
    return Layout(viewport_width=1280, viewport_height=900, boxes=boxes)


def test_render_fill_reference_explains_the_layout_check_only_with_a_layout():
    fields = [make_field(key) for key in ("a", "b", "c")]
    with_layout = render_fill_reference(make_page(fields, layout=stacked_layout("a", "b", "c")))
    without = render_fill_reference(make_page(fields))
    for state in ("`match`", "`resized`", "`blocked`", "`changed`"):
        assert state in with_layout
        assert state not in without


def test_render_fill_reference_never_lets_the_check_block_live_inspection():
    fields = [make_field(key) for key in ("a", "b", "c")]
    text = render_fill_reference(make_page(fields, layout=stacked_layout("a", "b", "c")))
    assert "never a gate" in text
    assert '{"verify": false}' in text


def test_render_fill_reference_explains_locate_only_with_a_manual_field():
    plain = render_fill_reference(make_page([make_field("a")]))
    upload = make_field("upload", strategy=Strategy.FILE)
    manual = render_fill_reference(make_page([make_field("a"), upload]))
    assert ".locate(" not in plain
    assert '.locate("upload")' in manual


def test_render_fill_reference_always_offers_the_short_rerun_call():
    assert ".run({...})" in render_fill_reference(make_page([make_field("a")]))


def test_the_skill_says_the_call_opens_a_closed_form():
    page = replace(make_page([make_field("a")]), open_steps=("text:Page settings",))
    text = render_skill_md(page)
    assert 'The form starts closed; the call opens it by clicking "Page settings".' in text
    assert 'Open the form by clicking "Page settings". Go down the field table' in text
    reference = render_fill_reference(page)
    assert 'opens it by clicking "Page settings", and only when it is closed' in reference


def test_render_skill_md_mentions_no_opening_for_a_form_shown_on_load():
    assert "open the form by clicking" not in render_skill_md(make_page([make_field("a")]))


def test_render_fill_reference_lists_views_and_how_the_call_walks_them():
    text = render_fill_reference(load_wizard_page())
    assert '2. Step 2: "Next".' in text
    assert '3. Contact dialog: "Add contact", then "Done" after filling.' in text
    assert "`stopped`" in text and "never clicks submit" in text


def test_render_fill_reference_without_views_says_nothing_about_them():
    assert "`stopped`" not in render_fill_reference(load_bench_page())
