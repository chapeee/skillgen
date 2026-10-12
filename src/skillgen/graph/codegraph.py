"""The code graph: a file-level view of the repository, built with Graphify.

This is the only module that imports `graphify`. Everything else works on the small
`CodeGraph` value it returns, so the rest of skillgen does not depend on Graphify's
node and edge formats.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any

from skillgen import TOOL_NAME
from skillgen.errors import GraphError

logger = logging.getLogger(__name__)

# Relations that mean "this file needs that file to build the page".
FOLLOWED_RELATIONS = frozenset(
    {
        "imports",
        "imports_from",
        "dynamic_import",
        "calls",
        "uses",
        "uses_component",
        "references",
        "re_exports",
        "inherits",
        "extends",
        "implements",
        "embeds",
        "requires",
        "indirect_call",
    }
)
_CALL_SUFFIX = re.compile(r"\(\)$")
# Labels of route nodes Graphify emits: Razor `route:/contact`, Dart `Route /contact`.
_ROUTE_LABEL = re.compile(r"^(?:route:|Route )(/\S*)$")
SNAPSHOT_VERSION = 1


@dataclass(frozen=True)
class SnapshotFile:
    """One recognized source or ignore-configuration file in a graph snapshot."""

    path: str
    size: int
    mtime_ns: int
    digest: str


@dataclass(frozen=True)
class SourceSnapshot:
    """The recognized Graphify input inventory and its exclusion configuration."""

    files: tuple[SnapshotFile, ...]
    excluded: tuple[str, ...] = ()
    config: tuple[SnapshotFile, ...] = ()
    version: int = SNAPSHOT_VERSION

    @property
    def fingerprint(self) -> str:
        """Return a stable fingerprint for this source snapshot."""
        document = {
            "version": self.version,
            "excluded": self.excluded,
            "files": [(item.path, item.digest) for item in self.files],
            "config": [(item.path, item.digest) for item in self.config],
        }
        return hashlib.sha256(
            json.dumps(document, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class CodeGraph:
    """Files and the dependencies between them.

    Attributes:
        files: Every code file, relative to the repository, sorted.
        edges: (from file, to file, relation) for each dependency between two files.
        symbols: Symbol name → files that define it (functions, classes, components).
        routes: (route, file) pairs for the few stacks whose routes Graphify extracts
            itself (Razor `@page`, Dart navigation).
        source_snapshot: The complete recognized Graphify input inventory, when cached.
    """

    files: tuple[str, ...]
    edges: tuple[tuple[str, str, str], ...]
    symbols: dict[str, tuple[str, ...]] = field(default_factory=dict)
    routes: tuple[tuple[str, str], ...] = ()
    source_snapshot: SourceSnapshot | None = None


def collapse_extraction(extraction: dict[str, Any]) -> CodeGraph:
    """Collapse Graphify's symbol-level extraction into a file-level graph.

    Args:
        extraction: The dictionary `graphify.extract.extract` returns.

    Returns:
        The file-level graph.
    """
    file_of: dict[str, str] = {}
    symbols: dict[str, set[str]] = {}
    for node in extraction.get("nodes", []):
        source_file = node.get("source_file")
        if not source_file:
            continue
        file_of[str(node["id"])] = str(source_file)
        label = _CALL_SUFFIX.sub("", str(node.get("label", "")))
        if label and label != Path(str(source_file)).name:
            symbols.setdefault(label, set()).add(str(source_file))
    edges = set()
    for edge in extraction.get("edges", []):
        relation = str(edge.get("relation", ""))
        source = file_of.get(str(edge.get("source")))
        target = file_of.get(str(edge.get("target")))
        if relation in FOLLOWED_RELATIONS and source and target and source != target:
            edges.add((source, target, relation))
    return CodeGraph(
        routes=find_route_nodes(extraction, file_of),
        files=tuple(sorted(set(file_of.values()))),
        edges=tuple(sorted(edges)),
        symbols={name: tuple(sorted(files)) for name, files in sorted(symbols.items())},
    )


def find_route_nodes(
    extraction: dict[str, Any], file_of: dict[str, str]
) -> tuple[tuple[str, str], ...]:
    """Find route nodes Graphify extracted, with the file that declares each.

    Args:
        extraction: Graphify's extraction.
        file_of: Node id → source file, for nodes that have one.

    Returns:
        (route, file) pairs, sorted.
    """
    routes: dict[str, str] = {}
    for node in extraction.get("nodes", []):
        found = _ROUTE_LABEL.match(str(node.get("label", "")))
        if found:
            routes[str(node["id"])] = found.group(1)
    pairs = {(route, file_of[nid]) for nid, route in routes.items() if nid in file_of}
    for edge in extraction.get("edges", []):
        target, source = str(edge.get("target")), str(edge.get("source"))
        if target in routes and source in file_of:
            pairs.add((routes[target], file_of[source]))
    return tuple(sorted(pairs))


def build_code_graph(
    repository: Path, cache_folder: Path, excluded: tuple[str, ...] = ()
) -> CodeGraph:
    """Extract the repository's code graph with Graphify.

    Graphify caches per-file results by content hash under `cache_folder`, so a
    rebuild after a small change only re-reads the changed files.

    Args:
        repository: The repository root.
        cache_folder: Where Graphify keeps its cache.
        excluded: Repository-relative folders to leave out, such as generated output.

    Returns:
        The file-level graph.

    Raises:
        GraphError: If Graphify is missing or fails.
    """
    try:
        from graphify.extract import (  # noqa: PLC0415 - heavy import, only when needed
            collect_files,
            extract,
        )
    except ImportError as error:
        raise GraphError(f"graphify is not installed; reinstall {TOOL_NAME}") from error
    root = repository.resolve()
    normalized_excluded = normalize_excluded(excluded)
    try:
        files = [
            path
            for path in collect_files(root, root=root)
            if not is_excluded(_relative_path(path, root), normalized_excluded)
        ]
        snapshot = build_source_snapshot_from_paths(root, files, normalized_excluded)
    except (OSError, RuntimeError, ValueError) as error:
        raise GraphError(f"graphify could not list source files: {error}") from error
    logger.info("graphify: extracting %d file(s)", len(files))
    cache_folder.mkdir(parents=True, exist_ok=True)
    try:
        extraction = extract(files, cache_root=cache_folder, root=root, parallel=False)
    except Exception as error:
        raise GraphError(f"graphify failed: {error}") from error
    return replace(collapse_extraction(extraction), source_snapshot=snapshot)


def build_source_snapshot(repository: Path, excluded: tuple[str, ...] = ()) -> SourceSnapshot:
    """Capture Graphify's recognized input files and ignore configuration.

    Args:
        repository: The repository root.
        excluded: Repository-relative generated paths to omit.

    Returns:
        A content-stamped source snapshot.

    Raises:
        GraphError: If Graphify cannot enumerate recognized files.
    """
    try:
        from graphify.extract import collect_files  # noqa: PLC0415 - lazy Graphify import
    except ImportError as error:
        raise GraphError(f"graphify is not installed; reinstall {TOOL_NAME}") from error
    root = repository.resolve()
    try:
        paths = collect_files(root, root=root)
    except (OSError, RuntimeError, ValueError) as error:
        raise GraphError(f"graphify could not list source files: {error}") from error
    return build_source_snapshot_from_paths(root, paths, normalize_excluded(excluded))


def build_source_snapshot_from_paths(
    root: Path, paths: list[Path], excluded: tuple[str, ...]
) -> SourceSnapshot:
    """Build a source snapshot from one Graphify file inventory."""
    normalized = normalize_excluded(excluded)
    files = tuple(
        sorted(
            (
                snapshot_file(
                    path if path.is_absolute() else root / path, _relative_path(path, root)
                )
                for path in paths
                if not is_excluded(_relative_path(path, root), normalized)
            ),
            key=lambda item: item.path,
        )
    )
    return SourceSnapshot(files=files, excluded=normalized, config=read_ignore_config(root))


def snapshot_file(path: Path, relative: str) -> SnapshotFile:
    """Stamp one file with filesystem metadata and a content digest."""
    try:
        stat = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise GraphError(f"could not snapshot {path}: {error}") from error
    return SnapshotFile(relative, stat.st_size, stat.st_mtime_ns, digest)


def read_ignore_config(root: Path) -> tuple[SnapshotFile, ...]:
    """Read the ignore files whose changes can alter Graphify's inventory."""
    candidates = [root / ".gitignore", root / ".graphifyignore"]
    git_folder = root / ".git"
    if git_folder.is_dir():
        candidates.append(git_folder / "info" / "exclude")
    elif git_folder.is_file():
        try:
            marker, location = git_folder.read_text(encoding="utf-8").strip().split(None, 1)
            if marker == "gitdir:":
                git_path = Path(location)
                candidates.append(
                    (git_path if git_path.is_absolute() else root / git_path) / "info" / "exclude"
                )
        except (OSError, ValueError):
            pass
    return tuple(
        snapshot_file(path, _relative_path(path, root)) for path in candidates if path.is_file()
    )


def normalize_excluded(excluded: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize and deduplicate generated paths used by Graphify."""
    return tuple(sorted({_normalise_relative(item) for item in excluded if item.strip("/\\")}))


def is_excluded(relative: str, excluded: tuple[str, ...]) -> bool:
    """Tell whether a path is a generated file or inside a generated directory."""
    return any(relative == item or relative.startswith(f"{item}/") for item in excluded)


def _relative_path(path: Path, root: Path) -> str:
    """Return a normalized repository-relative path."""
    candidate = path if path.is_absolute() else root / path
    return _normalise_relative(candidate.relative_to(root).as_posix())


def snapshot_to_dict(snapshot: SourceSnapshot | None) -> dict[str, Any] | None:
    """Convert a source snapshot to JSON, or omit it for legacy graphs."""
    if snapshot is None:
        return None
    return {
        "version": snapshot.version,
        "excluded": list(snapshot.excluded),
        "files": [snapshot_file_to_dict(item) for item in snapshot.files],
        "config": [snapshot_file_to_dict(item) for item in snapshot.config],
    }


def snapshot_file_to_dict(item: SnapshotFile) -> dict[str, Any]:
    """Convert one snapshot file to JSON."""
    return {
        "path": item.path,
        "size": item.size,
        "mtime_ns": item.mtime_ns,
        "digest": item.digest,
    }


def snapshot_from_dict(data: object) -> SourceSnapshot | None:
    """Read a source snapshot, returning none for a legacy or malformed cache."""
    if not isinstance(data, dict):
        return None
    try:
        version = int(data.get("version", 0))
        if version != SNAPSHOT_VERSION:
            return None
        return SourceSnapshot(
            files=tuple(snapshot_file_from_dict(item) for item in data.get("files", [])),
            excluded=tuple(str(item) for item in data.get("excluded", [])),
            config=tuple(snapshot_file_from_dict(item) for item in data.get("config", [])),
            version=version,
        )
    except (KeyError, TypeError, ValueError):
        return None


def snapshot_file_from_dict(data: object) -> SnapshotFile:
    """Read one snapshot file from JSON."""
    if not isinstance(data, dict):
        raise TypeError("snapshot file is not an object")
    return SnapshotFile(
        path=str(data["path"]),
        size=int(data["size"]),
        mtime_ns=int(data["mtime_ns"]),
        digest=str(data["digest"]),
    )


def graph_to_dict(graph: CodeGraph) -> dict[str, Any]:
    """Convert a graph to JSON for the cache.

    Args:
        graph: The graph.

    Returns:
        A JSON-ready dictionary.
    """
    return {
        "files": list(graph.files),
        "edges": [list(edge) for edge in graph.edges],
        "symbols": {name: list(files) for name, files in graph.symbols.items()},
        "routes": [list(pair) for pair in graph.routes],
        "source_snapshot": snapshot_to_dict(graph.source_snapshot),
    }


def graph_from_dict(data: dict[str, Any]) -> CodeGraph:
    """Read a graph from its cached JSON form.

    Args:
        data: The parsed JSON.

    Returns:
        The graph.
    """
    return CodeGraph(
        files=tuple(data.get("files", [])),
        edges=tuple((str(a), str(b), str(c)) for a, b, c in data.get("edges", [])),
        symbols={str(name): tuple(files) for name, files in data.get("symbols", {}).items()},
        routes=tuple((str(route), str(file)) for route, file in data.get("routes", [])),
        source_snapshot=snapshot_from_dict(data.get("source_snapshot")),
    )


def save_code_graph(graph: CodeGraph, path: Path) -> None:
    """Write the graph cache, stamped with the time it was built.

    Args:
        graph: The graph.
        path: The cache file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {**graph_to_dict(graph), "built_at": time.time()}
    temporary = path.with_suffix(f".{path.name}.tmp")
    temporary.write_text(json.dumps(document), encoding="utf-8")
    temporary.replace(path)


def find_graph_staleness(
    graph: CodeGraph, root: Path, built_at: float, excluded: tuple[str, ...] = ()
) -> str:
    """Say why a cached graph no longer matches the code, or nothing when it does.

    The cache has no other invalidation, and a stale graph is silently wrong rather
    than merely old: a route's component resolves to a file that has moved, or not at
    all, and the page is then sliced from the router that declares every route.

    New caches compare Graphify's complete recognized input inventory and content
    digests. Legacy caches retain the old conservative mtime check until rebuilt.

    Args:
        graph: The cached graph.
        root: The repository root.
        built_at: When the cache was written, as a Unix time.
        excluded: Repository-relative generated paths to ignore while checking folders.

    Returns:
        A short reason, or an empty string when the cache is current.
    """
    if not built_at:
        return f"it was cached before {TOOL_NAME} recorded build times"
    root = root.resolve()
    if graph.source_snapshot is None:
        return find_legacy_staleness(graph, root, built_at, excluded)
    try:
        current = build_source_snapshot(root, excluded)
    except GraphError:
        return compare_tracked_files(graph.source_snapshot, root)
    return compare_snapshots(graph.source_snapshot, current)


def compare_snapshots(expected: SourceSnapshot, current: SourceSnapshot) -> str:
    """Return a precise invalidation reason for two source snapshots."""
    if expected.excluded != current.excluded:
        return "source exclusions changed"
    if _snapshot_paths(expected.files) != _snapshot_paths(current.files):
        missing = sorted(_snapshot_paths(expected.files) - _snapshot_paths(current.files))
        if missing:
            return f"{missing[0]} is gone"
        return "source files were added or removed"
    expected_digests = _snapshot_digests(expected.files)
    current_digests = _snapshot_digests(current.files)
    for path in sorted(expected_digests):
        if expected_digests[path] != current_digests[path]:
            return f"{path} changed"
    if _snapshot_digests(expected.config) != _snapshot_digests(current.config):
        return "ignore configuration changed"
    return ""


def compare_tracked_files(snapshot: SourceSnapshot, root: Path) -> str:
    """Check tracked files when Graphify is unavailable for a full inventory."""
    for item in snapshot.files:
        path = root / item.path
        if not path.is_file():
            return f"{item.path} is gone"
        try:
            current = snapshot_file(path, item.path)
        except GraphError:
            return f"{item.path} could not be checked"
        if current.digest != item.digest:
            return f"{item.path} changed"
    return ""


def find_legacy_staleness(
    graph: CodeGraph, root: Path, built_at: float, excluded: tuple[str, ...] = ()
) -> str:
    """Conservatively check a pre-snapshot graph before it is migrated."""
    if excluded:
        try:
            current = build_source_snapshot(root, excluded)
        except GraphError:
            current = None
        if current is not None:
            expected = set(graph.files)
            actual = _snapshot_paths(current.files)
            if actual == expected:
                return ""
            missing = sorted(expected - actual)
            return f"{missing[0]} is gone" if missing else "files were added or removed"
    folders = {PurePosixPath(name).parent for name in graph.files}
    for name in graph.files:
        path = root / name
        if not path.exists():
            return f"{name} is gone"
        if path.stat().st_mtime > built_at:
            return f"{name} changed"
    for folder in sorted(folders):
        path = root / folder
        if path.is_dir() and path.stat().st_mtime > built_at:
            return f"files were added or removed in {folder or '.'}"
    return ""


def _normalise_relative(name: str) -> str:
    """Normalize one repository-relative path for comparison."""
    return PurePosixPath(name.replace("\\", "/")).as_posix()


def _snapshot_paths(items: tuple[SnapshotFile, ...]) -> set[str]:
    """Return paths in a snapshot."""
    return {item.path for item in items}


def _snapshot_digests(items: tuple[SnapshotFile, ...]) -> dict[str, str]:
    """Return path-to-content mappings for a snapshot."""
    return {item.path: item.digest for item in items}


def load_code_graph(path: Path) -> tuple[CodeGraph, float] | None:
    """Read the graph cache, or None when it does not exist or is unreadable.

    Args:
        path: The cache file.

    Returns:
        (the graph, when it was built as a Unix time), or None. The time is 0.0 for a
        cache written before build times were recorded.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return graph_from_dict(data), float(data.get("built_at") or 0.0)
    except (AttributeError, OSError, ValueError, TypeError):
        return None
