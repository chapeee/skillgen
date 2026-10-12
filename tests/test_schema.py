import pytest

from skillgen.errors import SchemaError
from skillgen.schema import find_schema_problems, load_schema, validate_document


def test_load_schema_reads_page_schema():
    assert load_schema("page")["type"] == "object"


def test_load_schema_rejects_unknown_name():
    with pytest.raises(SchemaError, match="no schema"):
        load_schema("nothing-here")


def test_find_schema_problems_reports_path():
    problems = find_schema_problems({"schema": "x.page/1", "route": "no-slash"}, "page")
    assert any(problem.startswith("route:") for problem in problems)


def test_validate_document_raises_with_problems():
    with pytest.raises(SchemaError) as caught:
        validate_document({}, "page")
    assert caught.value.problems
