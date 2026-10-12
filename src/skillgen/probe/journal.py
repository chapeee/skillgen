"""What discovery has already learnt about one page, kept so it is never learnt twice.

Discovery opens a page, reads what is on it, clicks something to reveal more and reads
again. Each of those costs a browser and, where a reader decides what to click, a model
call. So every state reached is written down as it is reached: a run that stops, fails
or hits a limit resumes from the last state instead of starting over, and a field found
once is never looked for again.

The journal only ever grows. A state is recorded once, by the clicks that reach it, and
re-reading the same state replaces that state's own record and nothing else.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from skillgen.workspace import write_json

logger = logging.getLogger(__name__)

JOURNAL_FILE = "discovery.json"
JOURNAL_SCHEMA = 1
# The state a page is in when it opens, before anything is clicked.
OPENING_STATE = ""


@dataclass(frozen=True)
class DiscoveredState:
    """One state of a page, and what was on it.

    Attributes:
        steps: The clicks that reach this state from the page as it opens, in order.
        fields: Field keys seen here, in the order the page showed them.
        clickables: What the page offered to click here, as the inventory reported it.
        tried: Steps already clicked from this state, whether or not they led anywhere.
        is_exhausted: True when nothing here is left worth clicking.
    """

    steps: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    clickables: tuple[dict[str, Any], ...] = ()
    tried: tuple[str, ...] = ()
    is_exhausted: bool = False

    @property
    def name(self) -> str:
        """The state's own name: its clicks joined, or empty for the opening state."""
        return " > ".join(self.steps)


@dataclass(frozen=True)
class Journal:
    """Everything discovery knows about one page so far.

    Attributes:
        route: The route being discovered.
        url: The address the page was opened at.
        states: Each state reached, in the order it was first reached.
        notes: What happened that a later run should not repeat, such as a click that
            left the page.
        model_calls: How many times a model has been asked to choose, for the cap.
    """

    route: str = ""
    url: str = ""
    states: tuple[DiscoveredState, ...] = ()
    notes: tuple[str, ...] = ()
    model_calls: int = 0

    def find(self, steps: Sequence[str]) -> DiscoveredState | None:
        """Return the state those clicks reach, or None when it is not recorded yet.

        Args:
            steps: The clicks from the page as it opens.

        Returns:
            The state, or None.
        """
        wanted = tuple(steps)
        return next((state for state in self.states if state.steps == wanted), None)

    @property
    def fields(self) -> tuple[str, ...]:
        """Every field key found in any state, in the order each was first seen."""
        seen: dict[str, None] = {}
        for state in self.states:
            seen.update(dict.fromkeys(state.fields))
        return tuple(seen)

    @property
    def is_finished(self) -> bool:
        """True when every state recorded has nothing left worth clicking."""
        return bool(self.states) and all(state.is_exhausted for state in self.states)


def record_state(journal: Journal, state: DiscoveredState) -> Journal:
    """Add a state, or replace the record of a state already reached.

    Args:
        journal: The journal so far.
        state: What was seen.

    Returns:
        The journal with that state recorded.
    """
    found = journal.find(state.steps)
    if found is None:
        return replace(journal, states=(*journal.states, state))
    kept = tuple(state if item.steps == state.steps else item for item in journal.states)
    return replace(journal, states=kept)


def record_tried(journal: Journal, steps: Sequence[str], step: str) -> Journal:
    """Note that a click was tried from a state, so it is never tried twice.

    Args:
        journal: The journal so far.
        steps: The clicks reaching the state the click was made from.
        step: The click that was tried.

    Returns:
        The journal with that click recorded.
    """
    state = journal.find(steps)
    if state is None or step in state.tried:
        return journal
    return record_state(journal, replace(state, tried=(*state.tried, step)))


def mark_exhausted(journal: Journal, steps: Sequence[str]) -> Journal:
    """Note that a state has nothing left worth clicking.

    Args:
        journal: The journal so far.
        steps: The clicks reaching that state.

    Returns:
        The journal with that state closed.
    """
    state = journal.find(steps)
    if state is None:
        return journal
    return record_state(journal, replace(state, is_exhausted=True))


def add_note(journal: Journal, note: str) -> Journal:
    """Record something a later run should not have to find out again.

    Args:
        journal: The journal so far.
        note: What happened, in one line.

    Returns:
        The journal with the note added, or unchanged when it is already there.
    """
    if not note or note in journal.notes:
        return journal
    return replace(journal, notes=(*journal.notes, note))


def count_model_call(journal: Journal) -> Journal:
    """Count one model call against the cap.

    Args:
        journal: The journal so far.

    Returns:
        The journal with the count raised.
    """
    return replace(journal, model_calls=journal.model_calls + 1)


def next_unexplored(journal: Journal) -> DiscoveredState | None:
    """Return the first recorded state that still has something worth clicking.

    States are returned in the order they were reached, so discovery finishes the part
    of the form a person would fill first before going deeper.

    Args:
        journal: The journal so far.

    Returns:
        The state, or None when every state is closed.
    """
    return next((state for state in journal.states if not state.is_exhausted), None)


def journal_to_dict(journal: Journal) -> dict[str, Any]:
    """Convert a journal to JSON.

    Args:
        journal: The journal.

    Returns:
        A JSON-ready dictionary.
    """
    return {
        "schema": JOURNAL_SCHEMA,
        "route": journal.route,
        "url": journal.url,
        "model_calls": journal.model_calls,
        "notes": list(journal.notes),
        "states": [
            {
                "steps": list(state.steps),
                "fields": list(state.fields),
                "clickables": list(state.clickables),
                "tried": list(state.tried),
                "exhausted": state.is_exhausted,
            }
            for state in journal.states
        ],
    }


def journal_from_dict(data: dict[str, Any]) -> Journal:
    """Read a journal back, ignoring a record written by a different layout.

    Args:
        data: The parsed JSON.

    Returns:
        The journal; an empty one when the record is from another schema.
    """
    if int(data.get("schema", 0)) != JOURNAL_SCHEMA:
        logger.info("ignoring a discovery journal written by another version")
        return Journal()
    return Journal(
        route=str(data.get("route", "")),
        url=str(data.get("url", "")),
        model_calls=int(data.get("model_calls", 0)),
        notes=tuple(str(note) for note in data.get("notes", [])),
        states=tuple(
            DiscoveredState(
                steps=tuple(str(step) for step in item.get("steps", [])),
                fields=tuple(str(key) for key in item.get("fields", [])),
                clickables=tuple(item.get("clickables", [])),
                tried=tuple(str(step) for step in item.get("tried", [])),
                is_exhausted=bool(item.get("exhausted", False)),
            )
            for item in data.get("states", [])
        ),
    )


def read_journal(folder: Path) -> Journal:
    """Read the journal of one page, or an empty one when there is none yet.

    Args:
        folder: The page's folder inside the workspace.

    Returns:
        What discovery already knows.
    """
    path = folder / JOURNAL_FILE
    if not path.is_file():
        return Journal()
    try:
        return journal_from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        logger.warning("could not read %s, starting discovery over: %s", path, error)
        return Journal()


def write_journal(folder: Path, journal: Journal) -> None:
    """Save the journal of one page, replacing what was there.

    Written after every state so that a run which stops, fails or runs out of model
    calls resumes from the last state rather than starting over.

    Args:
        folder: The page's folder inside the workspace.
        journal: What discovery knows now.
    """
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / JOURNAL_FILE, journal_to_dict(journal))
