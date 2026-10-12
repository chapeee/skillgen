"""Skill names and descriptions that follow the Agent Skills rules (spec section 4).

Names are lowercase letters, digits and single hyphens, at most 64 characters, and
equal to the folder name. The pattern is `<app>-<route-slug>`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from skillgen.errors import RouteError

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 299
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Route parameter spellings across routers: `:id`, `[id]`, `[...slug]`, `{id}`,
# `<int:id>`, `$id`, `*`. Recognising them is syntax, not framework knowledge:
# each only marks a segment as variable.
_PARAM_SEGMENT = re.compile(r"^(:.+|\[.+\]|\{.+\}|<.+>|\$.+|\*.*)$")
_PARAM_NAME = re.compile(r"[\w-]+")


def slugify(text: str) -> str:
    """Turn any text into lowercase words joined by single hyphens.

    Args:
        text: Free text, such as a title or route segment.

    Returns:
        The slug; empty when the text has no letters or digits.
    """
    lowered = text.lower()
    # Keep ASCII letters and digits only: names must pass the spec's character rule.
    words = re.findall(r"[a-z0-9]+", lowered)
    return "-".join(words)


def is_param_segment(segment: str) -> bool:
    """Tell whether a route segment is a parameter, such as `:id` or `[slug]`.

    Args:
        segment: One path segment without slashes.

    Returns:
        True for a parameter segment.
    """
    return bool(_PARAM_SEGMENT.match(segment))


def find_route_params(route: str) -> list[str]:
    """List the parameter names in a route pattern.

    Args:
        route: A route such as `/projects/:id/edit` or `/blog/[slug]`.

    Returns:
        Parameter names in order, such as `["id"]`.
    """
    names = []
    for segment in route.strip("/").split("/"):
        if is_param_segment(segment):
            # `<int:id>` names the parameter after the converter.
            inner = segment.split(":")[-1] if segment.startswith("<") else segment
            match = _PARAM_NAME.search(inner)
            names.append(match.group(0) if match else "param")
    return names


def slugify_route(route: str) -> str:
    """Turn a route pattern into a slug, dropping parameter segments.

    Args:
        route: The route, such as `/projects/:id/edit`.

    Returns:
        A slug such as `projects-edit`, or `home` for the root route.
    """
    segments = [s for s in route.strip("/").split("/") if s and not is_param_segment(s)]
    slug = slugify(" ".join(segments))
    return slug or "home"


def trim_name(name: str, max_length: int = MAX_NAME_LENGTH) -> str:
    """Shorten a slug to a maximum length, cutting at a hyphen when possible.

    Args:
        name: A valid slug.
        max_length: The longest allowed result.

    Returns:
        The slug, at most `max_length` characters, never ending with a hyphen.
    """
    if len(name) <= max_length:
        return name
    cut = name[:max_length]
    if "-" in cut and name[max_length] != "-":
        cut = cut.rsplit("-", 1)[0]
    return cut.strip("-")


def build_skill_name(app_name: str, route: str) -> str:
    """Build the skill name `<app>-<route-slug>` for a route.

    Args:
        app_name: The app's name; any text.
        route: The route pattern.

    Returns:
        A spec-valid name of at most 64 characters.

    Raises:
        RouteError: If no valid name can be built.
    """
    app_slug = slugify(app_name)
    route_slug = slugify_route(route)
    name = f"{app_slug}-{route_slug}" if app_slug else route_slug
    name = trim_name(name)
    if not is_valid_name(name):
        raise RouteError(f"cannot build a valid skill name for route {route!r}")
    return name


def is_valid_name(name: str) -> bool:
    """Tell whether a name follows the Agent Skills naming rules.

    Args:
        name: The candidate name.

    Returns:
        True when it is 1–64 lowercase letters, digits and single hyphens.
    """
    return 0 < len(name) <= MAX_NAME_LENGTH and bool(NAME_PATTERN.match(name))


def make_unique_names(names: Iterable[str]) -> list[str]:
    """Give repeated names a numeric suffix (`-2`, `-3`, …), keeping order.

    Args:
        names: Candidate names; the first occurrence keeps its name.

    Returns:
        Names in the same order, all different and all at most 64 characters.
    """
    taken: set[str] = set()
    result = []
    for name in names:
        candidate = name
        counter = 2
        while candidate in taken:
            suffix = f"-{counter}"
            candidate = trim_name(name, MAX_NAME_LENGTH - len(suffix)) + suffix
            counter += 1
        taken.add(candidate)
        result.append(candidate)
    return result


def build_description(
    title: str,
    route: str,
    app_name: str,
    topics: Iterable[str] = (),
    action: str = "",
) -> str:
    """Write a skill description under 300 characters (spec section 4 template).

    "Fills the <title> form at <route> in <app>: <topics>. Use when asked to <action>."
    Topics are dropped from the end until the text fits.

    Args:
        title: The page title.
        route: The route pattern.
        app_name: The app's display name.
        topics: The top field groups, most important first.
        action: What a user asks for, such as "create or update a project"; a generic
            phrase is used when empty.

    Returns:
        The description.
    """
    where = f" in {app_name}" if app_name else ""
    request = action or f"fill in, complete or submit the {title} form{where}"
    topic_list = [topic.strip() for topic in topics if topic.strip()]
    while True:
        middle = f": {_join_words(topic_list)}" if topic_list else ""
        text = f"Fills the {title} form at {route}{where}{middle}. Use when asked to {request}."
        if len(text) <= MAX_DESCRIPTION_LENGTH or not topic_list:
            break
        topic_list.pop()
    if len(text) > MAX_DESCRIPTION_LENGTH:
        text = text[: MAX_DESCRIPTION_LENGTH - 1].rstrip() + "…"
    return text


def _join_words(words: list[str]) -> str:
    """Join words as `a, b and c`, lower-casing all but proper-looking words."""
    lowered = [word[0].lower() + word[1:] if word[1:].islower() else word for word in words]
    if len(lowered) <= 2:
        return " and ".join(lowered)
    return ", ".join(lowered[:-1]) + " and " + lowered[-1]
