import json
import shutil
import subprocess

import pytest

from skillgen import TOOL_NAME
from skillgen.assets import read_fill_engine
from skillgen.generate.fill_script import (
    MAX_SCRIPT_BYTES,
    anchor_pattern,
    build_fill_script,
    compile_check,
    compile_field,
    compile_limits,
    count_lines,
    find_forbidden_syntax,
    find_host,
)
from skillgen.model.facts import Provenance, Source
from skillgen.model.page import Check, Condition, Limits, Operator, Rule, ValueType
from tests.helpers import load_bench_page, make_field, make_page


def test_read_fill_engine_is_es2019_only():
    assert find_forbidden_syntax(read_fill_engine()) == []


@pytest.mark.parametrize(
    ("source", "feature"),
    [
        ("a?.b", "optional chaining"),
        ("a ?? b", "nullish coalescing"),
        ("a ||= b", "logical assignment"),
        ("globalThis.x", "globalThis"),
        ("s.replaceAll('a', 'b')", "replaceAll"),
        ("list.at(-1)", "Array.at"),
        ("1_000", "numeric separator"),
    ],
)
def test_find_forbidden_syntax_flags_newer_features(source, feature):
    assert feature in find_forbidden_syntax(source)


def test_build_fill_script_stays_under_byte_limit_for_bench():
    script = build_fill_script(load_bench_page(), read_fill_engine())
    assert len(script.encode("utf-8")) <= MAX_SCRIPT_BYTES
    assert script.startswith(f"/* {TOOL_NAME} fill.js for skill bench-apply.")


def test_build_fill_script_packs_large_maps_under_limit():
    page = make_page([make_field(f"field_{index}") for index in range(150)])
    script = build_fill_script(page, read_fill_engine())
    assert len(script.encode("utf-8")) <= MAX_SCRIPT_BYTES
    assert count_lines(script) > 0


def test_build_fill_script_has_no_evidence_or_paths():
    script = build_fill_script(load_bench_page(), read_fill_engine())
    assert "EXTRACTED" not in script and "confidence" not in script


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_build_fill_script_parses_in_node(tmp_path):
    path = tmp_path / "fill.js"
    path.write_text(build_fill_script(load_bench_page(), read_fill_engine()), encoding="utf-8")
    result = subprocess.run(
        ["node", "--check", str(path)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_anchor_pattern_wraps_unanchored():
    assert anchor_pattern("[a-z]+") == "^(?:[a-z]+)$"
    assert anchor_pattern("^ab$") == "^ab$"


def test_compile_limits_keeps_numbers_numeric():
    compiled = compile_limits(Limits(minimum="1", maximum="9.5"), ValueType.NUMBER)
    assert compiled == {"mn": 1, "mx": 9.5}


def test_compile_limits_keeps_dates_as_text():
    assert compile_limits(Limits(minimum="2020-01-01"), ValueType.DATE) == {"mn": "2020-01-01"}


def test_compile_check_adds_message():
    assert compile_check(Check(pattern="^A"), "starts with A") == {"p": "^A", "m": "starts with A"}
    assert compile_check(Check()) is None


def test_compile_field_includes_conditions_and_rules():
    spec = make_field(
        "code",
        is_required=True,
        visible_if=Condition("kind", Operator.IN, ("Company",)),
        limits=Limits(max_length=8),
    )
    rule = Rule(
        text="Starts with X",
        provenance=Provenance((Source.USER_DEFINED,), 1.0),
        field="code",
        check=Check(pattern="^X"),
    )
    entry = compile_field(spec, [rule])
    assert entry == {
        "k": "code",
        "s": "#code",
        "t": "native-input",
        "r": 1,
        "vi": {"f": "kind", "o": "in", "v": ["Company"]},
        "x": [{"xl": 8}, {"p": "^X", "m": "Starts with X"}],
    }


def test_find_host_reads_hostname():
    assert find_host("https://admin.example.com:8443/base") == "admin.example.com"
    assert find_host("") == ""


def test_build_fill_script_embeds_valid_json_map():
    script = build_fill_script(load_bench_page(), read_fill_engine())
    line = next(line for line in script.splitlines() if line.startswith("  var SKILL = "))
    assert json.loads(line.removeprefix("  var SKILL = ").rstrip(";"))["host"] == "localhost"
