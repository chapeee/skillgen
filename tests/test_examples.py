import re

import pytest

from skillgen.generate.examples import (
    build_example_value,
    build_example_values,
    example_from_pattern,
)
from skillgen.model.page import Limits, ValueType
from tests.helpers import load_bench_page, make_field


@pytest.mark.parametrize(
    "pattern",
    ["[A-Z]{2}[0-9]{6}", "^[a-z0-9_]{3,20}$", r"\d{4}-\d{2}", "AB-[0-9]+", "x?y"],
)
def test_example_from_pattern_builds_matching_value(pattern):
    value = example_from_pattern(pattern)
    assert value is not None
    assert re.fullmatch(pattern.strip("^$"), value)


def test_example_from_pattern_gives_up_on_groups():
    assert example_from_pattern("(a|b)+") is None


def test_build_example_value_respects_length():
    spec = make_field("code", limits=Limits(min_length=30, max_length=40))
    value = build_example_value(spec)
    assert 30 <= len(value) <= 40


def test_build_example_value_uses_reserved_domains():
    assert build_example_value(make_field("mail", value_type=ValueType.EMAIL)).endswith(
        "@example.com"
    )


def test_build_example_value_skips_files_and_unlisted_options():
    assert build_example_value(make_field("doc", value_type=ValueType.FILE)) is None
    assert build_example_value(make_field("pick", value_type=ValueType.ENUM)) is None


def test_build_example_values_groups_rows():
    values = build_example_values(load_bench_page(), only_required=True)
    assert values["references"] == [{"name": "Sample reference name", "email": "alex@example.com"}]
    assert "bio" not in values
