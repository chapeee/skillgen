"""Find files that probably declare routes, from the shape of the code graph. Pure.

Graphify rarely names routes, but its links show hubs: a router file fans out to many
controllers, views or pages. These hubs, with what they link to, are the map Claude
reads to list routes in stacks no hint pack covers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from skillgen.graph.codegraph import CodeGraph
from skillgen.graph.slice import build_adjacency

# Generic words in file names that often mark routing or app entry files; none names a
# framework.
_NAME_HINT = re.compile(
    r"(^|[/_.-])(routes?|router|routing|urls|web|app|main|server|index|endpoints?)([/_.-]|$)", re.I
)
_TEST_PATH = re.compile(r"(^|/)(tests?|spec|__tests__|e2e)(/|$)|\.(test|spec)\.", re.I)
MAX_LINKS_SHOWN = 15


@dataclass(frozen=True)
class RouterHint:
    """A file that may declare routes.

    Attributes:
        file: Repository-relative path.
        links: Files it links to, as Graphify saw them (up to 15).
        score: Higher means more likely a router.
        reasons: Why it was picked, in words.
    """

    file: str
    links: tuple[str, ...]
    score: float
    reasons: tuple[str, ...]


def score_file(path: str, fan_out: int, has_route_nodes: bool) -> tuple[float, list[str]]:
    """Score how likely a file is to declare routes.

    Args:
        path: Repository-relative path.
        fan_out: Number of distinct files it links to.
        has_route_nodes: True when Graphify extracted routes from it.

    Returns:
        (score, reasons).
    """
    score, reasons = float(fan_out), [f"links to {fan_out} file(s)"] if fan_out else []
    # Only the file name counts: folders such as `app/` hold every kind of file.
    if _NAME_HINT.search(path.rsplit("/", 1)[-1]):
        score += 5
        reasons.append("its name suggests routing or an app entry")
    if has_route_nodes:
        score += 10
        reasons.append("Graphify found routes in it")
    return score, reasons


def rank_router_candidates(graph: CodeGraph, limit: int = 12) -> list[RouterHint]:
    """Rank files by how likely they are to declare routes.

    Args:
        graph: The code graph.
        limit: Most candidates to return.

    Returns:
        Candidates, most likely first; test files are left out.
    """
    adjacency = build_adjacency(graph)
    route_files = {file for _route, file in graph.routes}
    hints = []
    for path in graph.files:
        if _TEST_PATH.search(path):
            continue
        links = sorted(adjacency.get(path, set()))
        score, reasons = score_file(path, len(links), path in route_files)
        if score >= 3:
            hints.append(RouterHint(path, tuple(links[:MAX_LINKS_SHOWN]), score, tuple(reasons)))
    return sorted(hints, key=lambda hint: (-hint.score, hint.file))[:limit]
