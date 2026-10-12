from skillgen.errors import SchemaError, SkillgenError, ValidationFailedError, WorkspaceError


def test_errors_share_a_base():
    assert issubclass(WorkspaceError, SkillgenError)


def test_schema_error_summarises_problems():
    error = SchemaError("page", ["a: bad", "b: bad", "c: bad", "d: bad"])
    assert error.problems[3] == "d: bad"
    assert "a: bad; b: bad; c: bad" in str(error) and "d: bad" not in str(error)


def test_validation_failed_error_counts():
    assert str(ValidationFailedError(["x", "y"])).startswith("2 check(s) failed")
