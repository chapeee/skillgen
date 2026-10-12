"""The probe: pure classification here, and a real probe of the bench page (-m browser)."""

from __future__ import annotations

import json

import pytest

from skillgen.model.page import Box, Strategy, ValueType
from skillgen.probe.classify import build_probed_fields, classify, describe_shape, make_key

BENCH_URL = "http://localhost:8765/apply"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"kind": "choice", "type": "radio"}, (Strategy.CHOICE, ValueType.ENUM)),
        ({"kind": "choice", "type": "checkbox"}, (Strategy.CHOICE, ValueType.MULTI_ENUM)),
        ({"kind": "select", "type": "multiple"}, (Strategy.NATIVE_SELECT, ValueType.MULTI_ENUM)),
        ({"kind": "combobox", "type": "text"}, (Strategy.ARIA_COMBOBOX, ValueType.ENUM)),
        ({"kind": "tree", "type": "tree"}, (Strategy.ARIA_TREE, ValueType.PATH)),
        ({"kind": "rich-text"}, (Strategy.RICH_TEXT, ValueType.RICH_TEXT)),
        ({"kind": "file"}, (Strategy.FILE, ValueType.FILE)),
        ({"kind": "checkbox"}, (Strategy.NATIVE_INPUT, ValueType.BOOLEAN)),
        ({"kind": "input", "type": "email"}, (Strategy.NATIVE_INPUT, ValueType.EMAIL)),
        ({"kind": "input", "type": "textarea"}, (Strategy.NATIVE_INPUT, ValueType.LONG_TEXT)),
    ],
)
def test_classify_maps_controls(raw, expected):
    assert classify(raw) == expected


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ({"name": "full_name"}, "full_name"),
        ({"name": "references[0][email]"}, "references_email"),
        ({"id": "birthDate"}, "birthdate"),
        ({"label": "Date of birth"}, "date_of_birth"),
        ({"name": "2fa"}, "field_2fa"),
        ({}, "field"),
    ],
)
def test_make_key_derives_snake_case(raw, key):
    assert make_key(raw) == key


def test_build_probed_fields_keeps_keys_unique():
    fields = build_probed_fields([{"name": "a", "selector": "#a"}, {"name": "a", "selector": "#b"}])
    assert [f.key for f in fields] == ["a", "a_2"]


def test_describe_shape_keeps_types_never_values():
    shape = describe_shape(
        json.dumps({"name": "Ada", "age": 30, "tags": ["x"], "ok": True, "nested": {"n": None}})
    )
    assert shape == {
        "name": "string",
        "age": "number",
        "tags": ["string"],
        "ok": "boolean",
        "nested": {"n": "null"},
    }
    assert describe_shape("a=1&b=2") == {"a": "string", "b": "string"}


def test_build_probed_fields_carries_the_measured_box():
    control = {
        "tag": "input",
        "kind": "input",
        "type": "email",
        "label": "Email",
        "selector": "#email",
        "box": [306, 260, 654, 42],
    }
    hidden = {
        "tag": "input",
        "kind": "input",
        "type": "text",
        "label": "Company",
        "selector": "#company",
        "box": None,
    }
    measured, unseen = build_probed_fields([control, hidden])
    assert measured.box == Box(306, 260, 654, 42)
    assert unseen.box is None
