"""Merge route candidates from every source into `routes.json` entries."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from skillgen.errors import RouteError
from skillgen.model.route import RouteCandidate, RouteEntry, RouteTable
from skillgen.routes.naming import build_skill_name, is_valid_name, make_unique_names
from skillgen.routes.paths import is_route_wanted, is_windows_path, match_route, normalize_route


def check_skill_name(name: str) -> str:
    """Validate a skill name chosen by the developer.

    Args:
        name: The name.

    Returns:
        The same name.

    Raises:
        RouteError: If it breaks the Agent Skills naming rules.
    """
    if not is_valid_name(name):
        raise RouteError(
            f"skill name {name!r} must be 1–64 lowercase letters, digits and single hyphens "
            "(for example acme-signup)"
        )
    return name


def group_candidates(candidates: Iterable[RouteCandidate]) -> dict[str, list[RouteCandidate]]:
    """Group candidates by canonical route, keeping first-seen order.

    Args:
        candidates: Candidates from every source.

    Returns:
        Candidates by route.
    """
    grouped: dict[str, list[RouteCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(normalize_route(candidate.route), []).append(candidate)
    return grouped


def _merge_one(
    route: str, found: list[RouteCandidate], old: RouteEntry | None, prefix: str
) -> RouteEntry:
    files = tuple(dict.fromkeys(file for candidate in found for file in candidate.entry_files))
    sources = tuple(dict.fromkeys(candidate.source for candidate in found))
    title = next((candidate.title for candidate in found if candidate.title), "")
    if old is None:
        return RouteEntry(
            route=route,
            skill=build_skill_name(prefix, route),
            entry_files=files,
            sources=sources,
            title=title,
        )
    # The developer's choices in routes.json (name, title, skip, open steps) always survive.
    return RouteEntry(
        route=route,
        skill=old.skill if old.is_name_locked else build_skill_name(prefix, route),
        # The code is the source of truth: files found now replace the ones saved before.
        entry_files=files or old.entry_files,
        sources=tuple(dict.fromkeys((*old.sources, *sources))),
        title=old.title or title,
        has_form=old.has_form,
        is_skipped=old.is_skipped,
        is_name_locked=old.is_name_locked,
        open_steps=old.open_steps,
    )


def merge_routes(
    existing: RouteTable,
    candidates: Iterable[RouteCandidate],
    prefix: str,
    include: Iterable[str] = (),
    exclude: Iterable[str] = (),
) -> RouteTable:
    """Merge newly found routes with `routes.json`, keeping developer edits.

    Routes already in the table stay even when no source finds them now, since the
    developer may have added them by hand, unless nothing of the developer's would be
    lost (`is_stale`). A route that is really a Windows path is dropped.

    Args:
        existing: The current table.
        candidates: Routes found by every source.
        prefix: Skill-name prefix (the app's name or the developer's `--name`).
        include: Route globs to keep.
        exclude: Route globs to drop.

    Returns:
        The merged table, sorted by route, with unique skill names.
    """
    include_list, exclude_list = list(include), list(exclude)
    grouped = group_candidates(candidates)
    old_by_route = {entry.route: entry for entry in existing.entries}
    routes = sorted(set(grouped) | set(old_by_route))
    merged = [
        _merge_one(route, grouped.get(route, []), old_by_route.get(route), prefix)
        for route in routes
        if (is_route_wanted(route, include_list, exclude_list) or route in old_by_route)
        and not is_windows_path(route)
        and not (route not in grouped and is_stale(old_by_route[route]))
    ]
    return RouteTable(tuple(make_names_unique(merged)))


AUTOMATIC_SOURCE_PREFIXES = ("folder:", "router:", "graph:")


def is_stale(entry: RouteEntry) -> bool:
    """Whether a saved route no source finds any more can go without losing anything.

    It goes only when code discovery alone found it, the developer neither named,
    skipped nor opened it, and no skill was ever made from it.

    Args:
        entry: The saved route.

    Returns:
        True when it can be dropped.
    """
    is_automatic = bool(entry.sources) and all(
        source.startswith(AUTOMATIC_SOURCE_PREFIXES) for source in entry.sources
    )
    has_developer_choice = entry.is_name_locked or entry.is_skipped or bool(entry.open_steps)
    return is_automatic and not has_developer_choice and entry.has_form is None


def make_names_unique(entries: list[RouteEntry]) -> list[RouteEntry]:
    """Give clashing generated names a numeric suffix; locked names never change.

    Args:
        entries: Merged entries in route order.

    Returns:
        The entries with unique skill names.
    """
    taken = {entry.skill for entry in entries if entry.is_name_locked}
    result = []
    for entry in entries:
        if entry.is_name_locked:
            result.append(entry)
            continue
        name = make_unique_names([*sorted(taken), entry.skill])[-1]
        taken.add(name)
        result.append(replace(entry, skill=name))
    return result


def find_pattern_files(route: str, candidates: Iterable[RouteCandidate]) -> tuple[str, ...]:
    """Find the code files of the one route pattern a concrete route is an example of.

    A route written as one page, such as `/cms/locations/states/134`, is built by the
    code of `/cms/locations/:level/:id`. The pattern with the most fixed segments wins;
    when two fit equally well, nothing is guessed.

    Args:
        route: The concrete route.
        candidates: Routes found in the code.

    Returns:
        The pattern's entry files, or nothing when no single pattern fits.
    """
    scored = [
        (score, candidate)
        for candidate in candidates
        if (score := match_route(candidate.route, route)) is not None
    ]
    if not scored:
        return ()
    best = max(score for score, _ in scored)
    winners = [candidate for score, candidate in scored if score == best]
    if len({normalize_route(candidate.route) for candidate in winners}) != 1:
        return ()
    return tuple(dict.fromkeys(file for candidate in winners for file in candidate.entry_files))


def rename_route(table: RouteTable, route: str, name: str) -> RouteTable:
    """Give one route a developer-chosen skill name and lock it.

    Args:
        table: The current table.
        route: The route (or its current skill name).
        name: The new name.

    Returns:
        The updated table.

    Raises:
        RouteError: If the route is unknown, the name is invalid, or another route
            already uses the name.
    """
    check_skill_name(name)
    target = table.find(route)
    if target is None:
        raise RouteError(f"no route {route!r} in routes.json")
    if any(entry.skill == name and entry.route != target.route for entry in table.entries):
        raise RouteError(f"skill name {name!r} is already used by another route")
    updated = replace(target, skill=name, is_name_locked=True)
    return RouteTable(tuple(updated if e.route == target.route else e for e in table.entries))
