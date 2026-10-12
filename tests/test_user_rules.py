import pytest

from skillgen.errors import RuleError
from skillgen.generate.user_rules import (
    USER_END,
    USER_START,
    append_user_rule,
    extract_user_block,
    parse_check,
    parse_user_rules,
)
from skillgen.model.facts import Source
from skillgen.model.page import Check


def test_extract_user_block_returns_text_between_markers():
    text = f"# Title\n{USER_START}\n- Keep it short.\n{USER_END}\n"
    assert extract_user_block(text) == "- Keep it short."


def test_extract_user_block_is_empty_without_markers():
    assert extract_user_block("# nothing") == ""


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        ("legal_name ^A", ("legal_name", Check(pattern="^A"))),
        ("age min 18", ("age", Check(minimum=18.0))),
        ("age max 99", ("age", Check(maximum=99.0))),
        ("code length 4..8", ("code", Check(min_length=4, max_length=8))),
        ("start not-future", ("start", Check(is_not_future=True))),
    ],
)
def test_parse_check_reads_every_form(annotation, expected):
    assert parse_check(annotation) == expected


def test_parse_check_rejects_bad_regex():
    with pytest.raises(RuleError, match="regular expression"):
        parse_check("name ([")


def test_parse_check_needs_a_condition():
    with pytest.raises(RuleError):
        parse_check("lonely")


def test_parse_user_rules_compiles_annotated_lines():
    rules = parse_user_rules(
        '- Legal name must start with "A".  `check: legal_name ^A`\n- Be nice.\nnot a rule'
    )
    assert len(rules) == 2
    assert rules[0].field == "legal_name"
    assert rules[0].text == 'Legal name must start with "A".'
    assert rules[0].provenance.sources == (Source.USER_DEFINED,)
    assert rules[1].check is None


def test_append_user_rule_adds_line_with_check():
    block = append_user_rule("- First.", "Second rule", "code length 2..")
    assert block == "- First.\n- Second rule  `check: code length 2..`"


def test_append_user_rule_rejects_empty_text():
    with pytest.raises(RuleError):
        append_user_rule("", "   ")
