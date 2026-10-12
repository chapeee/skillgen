"""Page slices (the files that build one page) and change impact. Pure functions."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from skillgen.graph.codegraph import CodeGraph


@dataclass(frozen=True)
class PageSlice:
    """The files that build one page, nearest first.

    Attributes:
        files: (file, distance from an entry file) pairs, ranked by distance then path.
        is_truncated: True when the file or token cap cut the slice short.
        estimated_tokens: Estimated tokens of the files kept.
    """

    files: tuple[tuple[str, int], ...]
    is_truncated: bool = False
    estimated_tokens: int = 0

    @property
    def paths(self) -> tuple[str, ...]:
        """The file paths only, in slice order."""
        return tuple(path for path, _ in self.files)


def build_adjacency(graph: CodeGraph, *, is_reverse: bool = False) -> dict[str, set[str]]:
    """Build a file → neighbouring files map from the graph's edges.

    Args:
        graph: The code graph.
        is_reverse: Follow edges backwards (who depends on this file).

    Returns:
        The adjacency map.
    """
    adjacency: dict[str, set[str]] = {}
    for source, target, _relation in graph.edges:
        start, end = (target, source) if is_reverse else (source, target)
        adjacency.setdefault(start, set()).add(end)
    return adjacency


def walk_distances(
    adjacency: Mapping[str, set[str]], starts: Iterable[str], depth: int
) -> dict[str, int]:
    """Breadth-first distances from the start files, up to a depth.

    Args:
        adjacency: File → neighbours.
        starts: Files at distance 0.
        depth: Largest distance to reach.

    Returns:
        File → distance for every file reached.
    """
    distances = dict.fromkeys(starts, 0)
    queue = deque(distances)
    while queue:
        current = queue.popleft()
        if distances[current] >= depth:
            continue
        for neighbour in sorted(adjacency.get(current, ())):
            if neighbour not in distances:
                distances[neighbour] = distances[current] + 1
                queue.append(neighbour)
    return distances


# Package manifests and lockfiles describe dependencies, not pages.
MANIFEST_NAMES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "composer.json",
        "composer.lock",
        "pyproject.toml",
        "poetry.lock",
        "uv.lock",
        "Gemfile",
        "Gemfile.lock",
        "go.mod",
        "go.sum",
        "Cargo.toml",
        "Cargo.lock",
        "requirements.txt",
    }
)


def is_manifest(path: str) -> bool:
    """Tell whether a file is a package manifest or lockfile.

    Args:
        path: A repository-relative path.

    Returns:
        True for manifests such as `package.json`.
    """
    return path.rsplit("/", 1)[-1] in MANIFEST_NAMES


def slice_page(
    graph: CodeGraph,
    entry_files: Iterable[str],
    sizes: Mapping[str, int],
    *,
    context_files: Iterable[str] = (),
    depth: int = 3,
    max_files: int = 40,
    max_tokens: int = 60_000,
) -> PageSlice:
    """Find the files that build a page, nearest first, within the caps.

    Entry files are always kept, even when they alone exceed a cap. Context files
    (such as the router file that declares the route) are kept at distance 1 but not
    followed, so sibling pages they import stay out.

    Args:
        graph: The code graph.
        entry_files: The route's entry files.
        sizes: File → size in characters, for the token estimate.
        context_files: Files to include without following their imports.
        depth: Import hops to follow.
        max_files: Most files to keep.
        max_tokens: Most estimated tokens to keep (about four characters each).

    Returns:
        The slice.
    """
    entries = list(dict.fromkeys(entry_files))
    distances = walk_distances(build_adjacency(graph), entries, depth)
    for path in context_files:
        distances.setdefault(path, 1)
    ranked = sorted(
        (
            (path, distance)
            for path, distance in distances.items()
            if distance == 0 or not is_manifest(path)
        ),
        key=lambda item: (item[1], item[0]),
    )
    kept: list[tuple[str, int]] = []
    tokens = 0
    is_truncated = False
    for path, distance in ranked:
        cost = (sizes.get(path, 0) + 3) // 4
        is_entry = distance == 0
        if not is_entry and (len(kept) >= max_files or tokens + cost > max_tokens):
            is_truncated = True
            continue
        kept.append((path, distance))
        tokens += cost
    return PageSlice(files=tuple(kept), is_truncated=is_truncated, estimated_tokens=tokens)


def find_affected_files(graph: CodeGraph, changed: Iterable[str], depth: int = 2) -> set[str]:
    """Find files that depend on changed files within a number of hops.

    Args:
        graph: The code graph.
        changed: Changed files, relative to the repository.
        depth: Reverse hops to follow (the spec uses two).

    Returns:
        The changed files plus every file that depends on them within `depth`.
    """
    return set(walk_distances(build_adjacency(graph, is_reverse=True), changed, depth))


def find_stale_skills(slices: Mapping[str, Iterable[str]], affected: set[str]) -> list[str]:
    """List skills whose page slice touches an affected file.

    Args:
        slices: Skill name → files in its slice.
        affected: Files changed or depending on a change.

    Returns:
        Skill names, sorted.
    """
    return sorted(skill for skill, files in slices.items() if affected.intersection(files))


def resolve_component(graph: CodeGraph, name: str, declared_in: str) -> str | None:
    """Find the file that defines a component or view named in a route declaration.

    Names like `views.OrderEdit.as_view()` are tried from the most specific part
    outwards. A definition imported by the declaring file wins over others.

    Args:
        graph: The code graph.
        name: The captured name.
        declared_in: The file holding the route declaration.

    Returns:
        The defining file, or None when it cannot be resolved uniquely.
    """
    imported = build_adjacency(graph).get(declared_in, set())
    parts = [part for part in name.replace("()", "").split(".") if part]
    for part in reversed(parts):
        # Some languages label symbols with their module path (`AppWeb.SignupController`).
        files = tuple(
            dict.fromkeys(
                file
                for label, defined_in in graph.symbols.items()
                if label == part or label.endswith(f".{part}")
                for file in defined_in
            )
        )
        preferred = [file for file in files if file in imported]
        if len(preferred) == 1:
            return preferred[0]
        if len(files) == 1:
            return files[0]
    return find_imported_file_named(imported, parts[-1] if parts else "")


def find_imported_file_named(imported: set[str], name: str) -> str | None:
    """Find the one imported file named after a component, when no symbol defines it.

    A single-file component (`SignupView.vue`) declares no symbol of its own name; the
    route file imports it under its file name instead.

    Args:
        imported: Files the declaring file imports.
        name: The component name, such as `SignupView`.

    Returns:
        The file, or None when none or several match.
    """
    wanted = name.lower()
    found = [file for file in imported if PurePosixPath(file).stem.lower() == wanted]
    return found[0] if len(found) == 1 else None
