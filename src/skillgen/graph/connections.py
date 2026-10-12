"""How a page's files fit together, answered by Graphify's own commands.

`codegraph` collapses Graphify's extraction into file-to-file edges, which is all a
slice needs. An analysis needs more: which symbol a component declares, what it reaches
and by what relation, and where to look. Graphify answers that itself with `explain` and
`path`, so those are asked rather than reimplemented here.

The answers come from a graph Graphify builds into its own `graphify-out/` folder inside
the workspace cache. Building it costs seconds, so it is built once and reused until the
code changes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GRAPHIFY_EXECUTABLE = "graphify"
# Graphify writes `<out>/graphify-out/graph.json`, appending the folder name itself.
GRAPHIFY_OUT = "graphify-out"
GRAPH_FILE = "graph.json"
# A build walks the repository and parses every code file; a query reads one JSON file.
BUILD_TIMEOUT_SECONDS = 600
QUERY_TIMEOUT_SECONDS = 60
# An answer goes into a prompt, so it is bounded: enough for a component's own
# connections, not a hub's hundreds.
MAX_ANSWER_LINES = 40
GRAPHIFY_TOOL_VERSION = "graphify-code-only-v1"
EXPLAIN_CACHE_VERSION = "explain-v1"
GRAPH_META_SUFFIX = ".meta.json"


@dataclass(frozen=True)
class GraphifyGraph:
    """A built Graphify graph that queries can be asked of.

    Attributes:
        path: The `graph.json` Graphify wrote.
        fingerprint: The source snapshot fingerprint used to build it.
        tool_version: The Graphify build contract version.
        answer_cache: Folder for successful explain answers, if caching is enabled.
    """

    path: Path
    fingerprint: str = ""
    tool_version: str = GRAPHIFY_TOOL_VERSION
    answer_cache: Path | None = None


def find_graphify_command() -> str:
    """Return the `graphify` command, or an empty string when it is not installed.

    Returns:
        The resolved command, or "" when Graphify's CLI cannot be run.
    """
    return shutil.which(GRAPHIFY_EXECUTABLE) or ""


def _run_graphify(arguments: list[str], timeout_seconds: int, what: str) -> str | None:
    """Run one Graphify command and return its output, or nothing when it fails.

    Graphify is an aid, never a requirement: a failure leaves an analysis with the
    file list it always had rather than stopping a run.

    Args:
        arguments: Arguments after the command name.
        timeout_seconds: How long to wait.
        what: What is being asked, for the log.

    Returns:
        Standard output, or None when Graphify could not answer.
    """
    command = find_graphify_command()
    if not command:
        logger.debug("graphify's CLI is not installed; skipping %s", what)
        return None
    started = time.monotonic()
    try:
        result = subprocess.run(
            [command, *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.warning(
            "graphify %s failed after %.2fs: %s", what, time.monotonic() - started, error
        )
        return None
    if result.returncode != 0:
        logger.warning(
            "graphify %s exited %d after %.2fs: %s",
            what,
            result.returncode,
            time.monotonic() - started,
            result.stderr[:300],
        )
        return None
    logger.info("graphify %s finished in %.2fs", what, time.monotonic() - started)
    return result.stdout


def build_graph(
    repository: Path,
    cache_folder: Path,
    *,
    fingerprint: str = "",
    answer_cache: Path | None = None,
) -> GraphifyGraph | None:
    """Build the graph Graphify's queries read, into the workspace cache.

    `--code-only` keeps it to the AST pass, so no model is called and no API key is
    needed; `--no-cluster` skips community detection, which these questions do not use.

    Args:
        repository: The repository root.
        cache_folder: The workspace cache folder to build inside.
        fingerprint: The source snapshot fingerprint for the build.
        answer_cache: Folder for successful explain answers.

    Returns:
        The built graph, or None when Graphify could not build one.
    """
    cache_folder.mkdir(parents=True, exist_ok=True)
    graph_path = cache_folder / GRAPHIFY_OUT / GRAPH_FILE
    # Keep Graphify's in-progress output outside the repository so its own scan cannot
    # ingest a partially-written cache as source input.
    staging = Path(tempfile.mkdtemp(prefix=".graphify-build-"))
    logger.info("graphify: building the graph its queries read")
    try:
        output = _run_graphify(
            [
                "extract",
                str(repository),
                "--code-only",
                "--no-cluster",
                "--no-dedup",
                "--out",
                str(staging),
            ],
            BUILD_TIMEOUT_SECONDS,
            "extract",
        )
        staged = staging / GRAPHIFY_OUT / GRAPH_FILE
        if output is None or not _valid_graph_file(staged):
            logger.warning("graphify wrote no valid graph at %s", staged)
            return None
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        publish_graph_file(staged, graph_path)
        _write_graph_metadata(graph_path, fingerprint)
        return GraphifyGraph(
            path=graph_path,
            fingerprint=fingerprint,
            answer_cache=answer_cache,
        )
    except OSError as error:
        logger.warning("graphify graph publication failed: %s", error)
        return None
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def publish_graph_file(staged: Path, destination: Path) -> None:
    """Publish a staged graph atomically, even when the temp folder is another drive.

    Args:
        staged: The validated graph produced in the staging folder.
        destination: The cache path that queries should read.

    Raises:
        OSError: If the graph cannot be copied or published.
    """
    temporary = destination.with_suffix(f".{destination.name}.tmp")
    try:
        # The system temp folder can be on a different Windows drive from the workspace;
        # copying beside the destination makes the final replace atomic in all cases.
        shutil.copyfile(staged, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _valid_graph_file(path: Path) -> bool:
    """Check that Graphify produced a complete JSON graph before publishing it."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(document, dict) and isinstance(document.get("nodes"), list)


def graph_metadata_path(path: Path) -> Path:
    """Return the metadata sidecar path for a rich graph."""
    return path.with_name(path.name + GRAPH_META_SUFFIX)


def load_graph_metadata(path: Path) -> tuple[str, str] | None:
    """Read a rich graph fingerprint and tool version, or none when invalid."""
    try:
        data: Any = json.loads(graph_metadata_path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        fingerprint, tool_version = data.get("fingerprint"), data.get("tool_version")
        if not isinstance(fingerprint, str) or not fingerprint:
            return None
        if not isinstance(tool_version, str) or not tool_version:
            return None
        return fingerprint, tool_version
    except (OSError, ValueError, TypeError):
        return None


def _write_graph_metadata(path: Path, fingerprint: str) -> None:
    """Write metadata only after the staged rich graph has been published."""
    if not fingerprint:
        return
    metadata = graph_metadata_path(path)
    temporary = metadata.with_suffix(f".{metadata.name}.tmp")
    try:
        temporary.write_text(
            json.dumps({"fingerprint": fingerprint, "tool_version": GRAPHIFY_TOOL_VERSION}),
            encoding="utf-8",
        )
        temporary.replace(metadata)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        logger.debug("could not cache Graphify graph metadata: %s", error)


def explain_node(graph: GraphifyGraph, label: str) -> list[str]:
    """Ask Graphify to explain a node and what it connects to.

    Args:
        graph: The built graph.
        label: What to explain, such as a component name or a file name.

    Returns:
        Graphify's answer, one line per line, bounded; empty when it cannot answer.
    """
    cached = _read_explain_cache(graph, label)
    if cached is not None:
        return cached
    answer = _run_graphify(
        ["explain", label, "--graph", str(graph.path)], QUERY_TIMEOUT_SECONDS, f"explain {label}"
    )
    lines = _usable_lines(answer or "")
    if lines:
        _write_explain_cache(graph, label, lines)
    return lines


def find_path(graph: GraphifyGraph, source: str, target: str) -> list[str]:
    """Ask Graphify how one part of the code reaches another.

    Args:
        graph: The built graph.
        source: What to start from.
        target: What to reach.

    Returns:
        Graphify's answer, bounded; empty when there is no path or it cannot answer.
    """
    answer = _run_graphify(
        ["path", source, target, "--graph", str(graph.path)],
        QUERY_TIMEOUT_SECONDS,
        f"path {source} -> {target}",
    )
    return _usable_lines(answer or "")


def _usable_lines(answer: str) -> list[str]:
    """Keep an answer's own lines, dropping blanks and anything past the cap."""
    if not answer.strip() or answer.lstrip().startswith(("No node matching", "error:")):
        return []
    lines = [line.rstrip() for line in answer.splitlines() if line.strip()]
    return lines[:MAX_ANSWER_LINES]


def _explain_cache_path(graph: GraphifyGraph, label: str) -> Path | None:
    """Return the cache path for a valid graph fingerprint and label."""
    if not graph.answer_cache or not graph.fingerprint:
        return None
    key = json.dumps(
        {
            "version": EXPLAIN_CACHE_VERSION,
            "tool": graph.tool_version,
            "fingerprint": graph.fingerprint,
            "label": label,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return graph.answer_cache / f"{hashlib.sha256(key).hexdigest()}.json"


def _read_explain_cache(graph: GraphifyGraph, label: str) -> list[str] | None:
    """Read a successful explain answer, ignoring corrupt or stale cache files."""
    path = _explain_cache_path(graph, label)
    if path is None or not path.is_file():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
        lines = data.get("lines") if isinstance(data, dict) else None
        if isinstance(lines, list) and lines and all(isinstance(item, str) for item in lines):
            return lines[:MAX_ANSWER_LINES]
    except (OSError, ValueError, TypeError):
        return None
    return None


def _write_explain_cache(graph: GraphifyGraph, label: str, lines: list[str]) -> None:
    """Persist one usable explain answer without making cache failure consequential."""
    path = _explain_cache_path(graph, label)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{path.name}.tmp")
        temporary.write_text(json.dumps({"lines": lines}), encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        logger.debug("could not cache Graphify explain output: %s", error)
