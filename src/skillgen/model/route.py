"""Entries of `routes.json` and `questions.json`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RouteCandidate:
    """A route found by one discovery source, before merging.

    Attributes:
        route: The route pattern, such as `/projects/:id/edit`.
        source: Which probe found it, such as `folder:nextjs-app` or `user`.
        entry_files: Files that build the page, relative to the repository.
        title: A title, when the source knows one.
    """

    route: str
    source: str
    entry_files: tuple[str, ...] = ()
    title: str = ""


@dataclass(frozen=True)
class RouteEntry:
    """One route in `routes.json`. Developers may edit `skill`, `title`, `is_skipped`, `open`.

    Attributes:
        route: The route pattern.
        skill: The skill name; chosen by the developer or built from the route.
        entry_files: Files that build the page, relative to the repository.
        sources: Every discovery source that found the route.
        title: The page title, when known.
        has_form: True or False once known; None before analysis.
        is_skipped: True when the developer chose not to generate a skill.
        is_name_locked: True when the developer chose the name; merging keeps it.
        open_steps: What to click, in order, before the form is on screen: a CSS selector
            or `text:Label`. Empty when the form shows as the page opens.
    """

    route: str
    skill: str
    entry_files: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    title: str = ""
    has_form: bool | None = None
    is_skipped: bool = False
    is_name_locked: bool = False
    open_steps: tuple[str, ...] = ()


@dataclass(frozen=True)
class Question:
    """A fact that needs the developer before it can go into a skill.

    Attributes:
        id: Stable id used by `answer`.
        skill: The skill the question belongs to.
        subject: What it is about, such as `field:email:required`.
        text: The question in words.
        choices: Suggested answers; any text is accepted.
        answer: The developer's answer, empty until answered.
    """

    id: str
    skill: str
    subject: str
    text: str
    choices: tuple[str, ...] = ()
    answer: str = ""


def route_entry_to_dict(entry: RouteEntry) -> dict[str, Any]:
    """Convert a route entry to its JSON form.

    Args:
        entry: The entry.

    Returns:
        The JSON object.
    """
    data: dict[str, Any] = {
        "route": entry.route,
        "skill": entry.skill,
        "title": entry.title,
        "entry_files": list(entry.entry_files),
        "sources": list(entry.sources),
        "has_form": entry.has_form,
        "skip": entry.is_skipped,
        "name_locked": entry.is_name_locked,
    }
    # Written only when set, so routes.json does not grow a key on every route.
    if entry.open_steps:
        data["open"] = list(entry.open_steps)
    return data


def route_entry_from_dict(data: dict[str, Any]) -> RouteEntry:
    """Read a route entry from its JSON form.

    Args:
        data: The JSON object.

    Returns:
        The entry.
    """
    has_form = data.get("has_form")
    return RouteEntry(
        route=str(data["route"]),
        skill=str(data.get("skill", "")),
        entry_files=tuple(str(item) for item in data.get("entry_files", [])),
        sources=tuple(str(item) for item in data.get("sources", [])),
        title=str(data.get("title", "")),
        has_form=None if has_form is None else bool(has_form),
        is_skipped=bool(data.get("skip", False)),
        is_name_locked=bool(data.get("name_locked", False)),
        open_steps=tuple(str(step) for step in data.get("open", []) if str(step).strip()),
    )


def question_to_dict(question: Question) -> dict[str, Any]:
    """Convert a question to its JSON form.

    Args:
        question: The question.

    Returns:
        The JSON object.
    """
    return {
        "id": question.id,
        "skill": question.skill,
        "subject": question.subject,
        "text": question.text,
        "choices": list(question.choices),
        "answer": question.answer,
    }


def question_from_dict(data: dict[str, Any]) -> Question:
    """Read a question from its JSON form.

    Args:
        data: The JSON object.

    Returns:
        The question.
    """
    return Question(
        id=str(data["id"]),
        skill=str(data.get("skill", "")),
        subject=str(data.get("subject", "")),
        text=str(data.get("text", "")),
        choices=tuple(str(item) for item in data.get("choices", [])),
        answer=str(data.get("answer", "")),
    )


@dataclass(frozen=True)
class RouteTable:
    """All routes, in route order.

    Attributes:
        entries: The routes.
    """

    entries: tuple[RouteEntry, ...] = field(default_factory=tuple)

    def find(self, route_or_skill: str) -> RouteEntry | None:
        """Find an entry by route or by skill name.

        Args:
            route_or_skill: A route such as `/signup` or a skill name.

        Returns:
            The entry, or None.
        """
        for entry in self.entries:
            if route_or_skill in (entry.route, entry.skill):
                return entry
        return None
