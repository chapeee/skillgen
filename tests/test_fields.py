from skillgen.compile.fields import FieldContext, assess_field, build_field, find_probed_field
from skillgen.compile.merge import MergeInput, build_page_model
from skillgen.model.page import Strategy, ValueType
from skillgen.model.probe import ProbedField, ProbedPage

FIELD = {
    "key": "email",
    "label": "Email",
    "type": "email",
    "required": True,
    "strategy": "native-input",
    "selector": "#email",
    "evidence": [{"file": "src/Form.tsx", "line": 3}],
}
ANALYSIS = {"has_form": True, "title": "Join", "fields": [FIELD], "submit": {"selector": "button"}}


def probed(key="email", **changes):
    base = {
        "key": key,
        "label": "Email",
        "selector": f"#{key}",
        "strategy": Strategy.NATIVE_INPUT,
        "value_type": ValueType.EMAIL,
        "is_required": True,
        "is_proven": True,
        "name": key,
    }
    return ProbedField(**(base | changes))


def merge(analysis=ANALYSIS, probe=None, answers=None):
    return build_page_model(
        MergeInput(
            route="/join",
            skill="demo-join",
            analysis=analysis,
            app_name="Demo",
            probe=probe,
            answers=answers or {},
        )
    )


def test_build_field_needs_identity():
    context = FieldContext("s", {})
    results = assess_field(FIELD | {"inferred": ["selector"]}, context)
    assert build_field(FIELD, results) is None


def test_find_probed_field_matches_by_label_and_ignores_groups():
    probe = ProbedPage(url="u", title="t", fields=(probed("mail", selector="#mail"),))
    assert find_probed_field(FIELD | {"selector": "#x"}, probe) is not None
    assert find_probed_field(FIELD | {"group": "rows"}, probe) is None
