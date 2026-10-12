from skillgen.model.facts import Source
from skillgen.model.page import (
    Condition,
    Operator,
    OptionsSource,
    find_field,
    list_dependencies,
    make_provenance,
)
from tests.helpers import make_field, make_page


def test_find_field_by_key():
    page = make_page([make_field("a"), make_field("b")])
    assert find_field(page, "b") is page.fields[1]
    assert find_field(page, "c") is None


def test_list_dependencies_in_fill_order():
    page = make_page(
        [
            make_field("country"),
            make_field("region", options_from=OptionsSource(depends_on="country", is_async=True)),
            make_field(
                "vat",
                visible_if=Condition("kind", Operator.IN, ("Company",)),
                required_if=Condition("kind", Operator.IN, ("Company",)),
            ),
        ]
    )
    assert [(d.source, d.target, d.kind) for d in list_dependencies(page)] == [
        ("country", "region", "options_from"),
        ("kind", "vat", "visible_if"),
        ("kind", "vat", "required_if"),
    ]


def test_make_provenance_rounds():
    assert make_provenance((Source.EXTRACTED,), 0.123456).confidence == 0.123
