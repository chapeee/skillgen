"""Route path shapes: one canonical form for routes from any source."""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable

from skillgen.errors import RouteError

# A drive letter at the start, with or without the leading slash: `/C:/...`, `C:\...`.
_WINDOWS_PATH = re.compile(r"^/?[A-Za-z]:[/\\]")

_QUOTES = "'\"`"
# Parameter spellings: `{id}`, `<int:id>`, `[id]`, `[...slug]`, `$id`, `:id`. Each
# becomes `:name`. This is syntax recognition only; it names no framework.
_PARAM_FORMS = (
    re.compile(r"^\{(?P<name>\w+)\??\}$"),
    re.compile(r"^<(?:\w+:)?(?P<name>\w+)>$"),
    re.compile(r"^\[\[?(?:\.\.\.)?(?P<name>\w+)\]?\]$"),
    re.compile(r"^\$(?P<name>\w+)$"),
    re.compile(r"^:(?P<name>\w+)\??$"),
)


def strip_quotes(text: str) -> str:
    """Remove one pair of surrounding quotes from a captured string literal.

    Args:
        text: Such as `'/signup'` or `"/signup"`.

    Returns:
        The text inside the quotes, or the text unchanged.
    """
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in _QUOTES:
        return text[1:-1]
    return text


def normalize_segment(segment: str) -> str:
    """Rewrite a parameter segment as `:name`; other segments are unchanged.

    Args:
        segment: One path part.

    Returns:
        The canonical segment.
    """
    for form in _PARAM_FORMS:
        match = form.match(segment)
        if match:
            return f":{match.group('name')}"
    return segment


def normalize_route(text: str) -> str:
    """Bring a route from any source to the canonical `/a/:id/b` form.

    Args:
        text: A route as written in code, a URL path, or user input.

    Returns:
        The canonical route: leading slash, no trailing slash, `:name` parameters,
        no query string or fragment.
    """
    path = strip_quotes(text).split("?", 1)[0].split("#", 1)[0].strip()
    segments = [normalize_segment(part) for part in path.split("/") if part and part != "."]
    return "/" + "/".join(segments)


def is_windows_path(route: str) -> bool:
    """Whether a route is really a Windows path, such as Git Bash makes of `/forms/x`.

    Args:
        route: The route as given or saved.

    Returns:
        True for `/C:/Program Files/Git/forms/x` and the like.
    """
    return bool(_WINDOWS_PATH.match(route))


def check_route_text(route: str) -> None:
    """Refuse a route that is really a Windows path, as Git Bash makes of `/forms/x`.

    Git Bash rewrites any argument starting with `/` into a path under its own folder,
    so `--route /forms/x` arrives as `C:/Program Files/Git/forms/x` and would be saved.

    Args:
        route: The route as given.

    Raises:
        RouteError: If it looks like a Windows path.
    """
    if is_windows_path(route):
        raise RouteError(
            f"{route!r} is a Windows path, not a route: Git Bash rewrote a route that starts "
            "with /. Put MSYS_NO_PATHCONV=1 in front of the command, or run it in PowerShell."
        )


def match_route(pattern: str, route: str) -> int | None:
    """Tell whether a concrete route is an example of a route pattern, and how closely.

    `/cms/locations/:level/:id` fits `/cms/locations/states/134`: each `:name` stands for
    any one segment, and every other segment must be equal.

    Args:
        pattern: A route as found in the code, with `:name` parameters.
        route: A route, usually one concrete page.

    Returns:
        How many fixed segments matched (more is more specific), or None when the route
        does not fit the pattern.
    """
    wanted = normalize_route(pattern).strip("/").split("/")
    given = normalize_route(route).strip("/").split("/")
    if len(wanted) != len(given):
        return None
    fixed = 0
    for part, value in zip(wanted, given, strict=True):
        if part.startswith(":"):
            continue
        if part != value:
            return None
        fixed += 1
    return fixed


def is_route_wanted(route: str, include: Iterable[str], exclude: Iterable[str]) -> bool:
    """Apply include and exclude globs (`developer/*`) to a route.

    Globs are matched against the route with and without its leading slash.

    Args:
        route: The canonical route.
        include: Globs to keep; an empty list keeps everything.
        exclude: Globs to drop.

    Returns:
        True when the route should be kept.
    """
    forms = (route, route.lstrip("/"))

    def matches(globs: Iterable[str]) -> bool:
        return any(fnmatch.fnmatchcase(form, glob) for glob in globs for form in forms)

    include_list = list(include)
    return (not include_list or matches(include_list)) and not matches(exclude)
