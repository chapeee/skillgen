from skillgen.model.route import (
    Question,
    RouteEntry,
    RouteTable,
    question_from_dict,
    question_to_dict,
    route_entry_from_dict,
    route_entry_to_dict,
)


def test_route_entry_round_trip():
    entry = RouteEntry(
        "/a", "x-a", ("a.tsx",), ("user",), "A", has_form=None, is_skipped=True, is_name_locked=True
    )
    assert route_entry_from_dict(route_entry_to_dict(entry)) == entry


def test_question_round_trip():
    question = Question("q1", "x", "rule:1", "Keep it?", ("yes", "no"), "yes")
    assert question_from_dict(question_to_dict(question)) == question


def test_route_table_find_by_route_or_skill():
    table = RouteTable((RouteEntry("/a", "x-a"),))
    assert table.find("/a") == table.find("x-a") == table.entries[0]
    assert table.find("/b") is None
