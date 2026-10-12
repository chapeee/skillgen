"""The discovery journal: what a page has already shown, so it is never asked twice.

Every state discovery reaches costs a browser and, where a reader chooses the click, a
model call. The journal is written after each state so a run that stops, fails or runs
out of model calls resumes from the last one.
"""

from __future__ import annotations

from skillgen.probe.journal import (
    JOURNAL_FILE,
    OPENING_STATE,
    DiscoveredState,
    Journal,
    add_note,
    count_model_call,
    journal_from_dict,
    journal_to_dict,
    mark_exhausted,
    next_unexplored,
    read_journal,
    record_state,
    record_tried,
    write_journal,
)

OPENING = DiscoveredState(
    fields=("first_name", "last_name"),
    clickables=({"label": "Next", "step": "#next"},),
)
STEP_TWO = DiscoveredState(steps=("#next",), fields=("department",))


def test_a_state_is_named_by_the_clicks_that_reach_it():
    assert OPENING.name == OPENING_STATE
    assert DiscoveredState(steps=("#next", "text:Add contact")).name == "#next > text:Add contact"


def test_record_state_adds_a_state_the_first_time_it_is_reached():
    journal = record_state(record_state(Journal(), OPENING), STEP_TWO)
    assert [state.name for state in journal.states] == ["", "#next"]


def test_record_state_replaces_only_that_states_own_record():
    """Re-reading a state must not disturb what every other state found."""
    journal = record_state(record_state(Journal(), OPENING), STEP_TWO)
    again = record_state(journal, DiscoveredState(steps=("#next",), fields=("department", "site")))
    assert len(again.states) == 2
    assert (again.find(()) or OPENING).fields == ("first_name", "last_name")
    assert (again.find(("#next",)) or STEP_TWO).fields == ("department", "site")


def test_every_field_found_anywhere_is_kept_in_the_order_first_seen():
    journal = record_state(record_state(Journal(), OPENING), STEP_TWO)
    assert journal.fields == ("first_name", "last_name", "department")


def test_a_field_seen_in_two_states_is_reported_once():
    both = DiscoveredState(steps=("#next",), fields=("last_name", "department"))
    journal = record_state(record_state(Journal(), OPENING), both)
    assert journal.fields == ("first_name", "last_name", "department")


def test_record_tried_remembers_a_click_so_it_is_never_tried_twice():
    journal = record_tried(record_state(Journal(), OPENING), (), "#next")
    assert (journal.find(()) or OPENING).tried == ("#next",)
    # Recording the same click again changes nothing.
    assert record_tried(journal, (), "#next") == journal


def test_record_tried_ignores_a_state_that_was_never_reached():
    journal = record_state(Journal(), OPENING)
    assert record_tried(journal, ("#never",), "#x") == journal


def test_next_unexplored_returns_states_in_the_order_they_were_reached():
    journal = record_state(record_state(Journal(), OPENING), STEP_TWO)
    assert (next_unexplored(journal) or STEP_TWO).name == ""
    closed = mark_exhausted(journal, ())
    assert (next_unexplored(closed) or OPENING).name == "#next"
    assert next_unexplored(mark_exhausted(closed, ("#next",))) is None


def test_a_journal_is_finished_only_when_every_state_is_closed():
    journal = record_state(record_state(Journal(), OPENING), STEP_TWO)
    assert Journal().is_finished is False
    assert journal.is_finished is False
    assert mark_exhausted(mark_exhausted(journal, ()), ("#next",)).is_finished is True


def test_a_note_is_kept_once_so_a_later_run_does_not_repeat_the_finding():
    journal = add_note(
        add_note(Journal(), "Dashboard leaves the page"), "Dashboard leaves the page"
    )
    assert journal.notes == ("Dashboard leaves the page",)
    assert add_note(journal, "").notes == journal.notes


def test_model_calls_are_counted_for_the_cap():
    assert count_model_call(count_model_call(Journal())).model_calls == 2


def test_a_journal_round_trips_through_json():
    journal = count_model_call(
        add_note(
            record_tried(
                record_state(record_state(Journal(route="/a", url="u"), OPENING), STEP_TWO),
                (),
                "#next",
            ),
            "a note",
        )
    )
    assert journal_from_dict(journal_to_dict(journal)) == journal


def test_a_journal_from_another_layout_is_ignored_rather_than_misread():
    stale = {**journal_to_dict(record_state(Journal(), OPENING)), "schema": 99}
    assert journal_from_dict(stale) == Journal()


def test_a_journal_survives_a_stop_and_resumes_from_the_last_state(tmp_path):
    journal = record_state(record_state(Journal(route="/a", url="u"), OPENING), STEP_TWO)
    write_journal(tmp_path, mark_exhausted(journal, ()))
    resumed = read_journal(tmp_path)
    assert resumed.fields == ("first_name", "last_name", "department")
    assert (next_unexplored(resumed) or OPENING).name == "#next"


def test_no_journal_yet_and_an_unreadable_one_both_start_empty(tmp_path):
    assert read_journal(tmp_path) == Journal()
    (tmp_path / JOURNAL_FILE).write_text("not json", encoding="utf-8")
    assert read_journal(tmp_path) == Journal()
