from skillgen.compile.assess import (
    MISSING,
    apply_answer,
    assess_fact,
    describe_value,
    make_question_id,
)
from skillgen.model.facts import Source


def test_assess_fact_code_only_extracted_is_usable():
    found = assess_fact("s", "field:a:required", True, Source.EXTRACTED)
    assert (
        found.value is True
        and found.confidence == 0.85
        and found.is_usable
        and found.question is None
    )


def test_assess_fact_inferred_asks_and_is_not_usable():
    found = assess_fact("s", "field:a:required", True, Source.CLAUDE_INFERRED)
    assert not found.is_usable
    assert found.question is not None and found.question.choices == ("yes", "no")


def test_assess_fact_agreement_combines_sources():
    found = assess_fact("s", "field:a:required", True, Source.EXTRACTED, page_value=True)
    assert found.confidence == 0.985
    assert found.sources == (Source.EXTRACTED, Source.RUNTIME_PROBED)


def test_assess_fact_conflict_caps_and_asks():
    found = assess_fact("s", "field:a:required", True, Source.EXTRACTED, page_value=False)
    assert found.confidence == 0.5 and not found.is_usable
    assert found.question is not None and "disagree" in found.question.text


def test_assess_fact_page_only():
    found = assess_fact("s", "x", MISSING, Source.EXTRACTED, page_value="#a")
    assert found.value == "#a" and found.sources == (Source.RUNTIME_PROBED,)


def test_assess_fact_nothing_known():
    assert assess_fact("s", "x", MISSING, Source.EXTRACTED).value is None


def test_assess_fact_answer_wins():
    found = assess_fact("s", "x", True, Source.EXTRACTED, page_value=False, answers={"x": "page"})
    assert found.value is False and found.confidence == 1.0
    assert found.sources == (Source.DEVELOPER_CONFIRMED,)


def test_apply_answer_handles_yes_no_and_text():
    assert apply_answer("yes", 1, MISSING, str).value == 1
    assert apply_answer("no", 1, MISSING, str).is_dropped
    assert apply_answer("A, B", 1, MISSING, lambda text: text.split(", ")).value == ["A", "B"]


def test_make_question_id_is_stable():
    assert make_question_id("s", "x") == make_question_id("s", "x")
    assert make_question_id("s", "x") != make_question_id("s", "y")


def test_describe_value_formats():
    assert describe_value(True) == "yes"
    assert describe_value(["a", "b"]) == "a · b"
    assert describe_value([]) == "(empty)"
