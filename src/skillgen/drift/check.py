"""Find routes whose skills are stale after code changes (spec section 9).

A route is stale when a changed file is in its page slice, or something in its slice
depends on a changed file within two hops.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from skillgen.errors import WorkspaceError
from skillgen.graph.codegraph import CodeGraph
from skillgen.graph.slice import find_affected_files, find_stale_skills
from skillgen.workspace import Workspace

logger = logging.getLogger(__name__)

IMPACT_DEPTH = 2


@dataclass(frozen=True)
class DriftReport:
    """Which skills need regenerating.

    Attributes:
        changed_files: Files changed since the reference.
        stale_skills: Skills whose slice touches a change.
        unknown_skills: Skills without a saved slice (never generated, or generated
            before slices were saved); regenerate them to be safe.
    """

    changed_files: tuple[str, ...]
    stale_skills: tuple[str, ...]
    unknown_skills: tuple[str, ...] = ()


def list_changed_files(root: Path, since: str) -> list[str]:
    """List files changed since a git reference, plus uncommitted and untracked ones.

    Args:
        root: The repository root.
        since: A git reference such as `HEAD~1` or a commit hash.

    Returns:
        Repository-relative paths, sorted.

    Raises:
        WorkspaceError: If git fails (not a repository, unknown reference).
    """
    commands = (
        ["git", "diff", "--name-only", since, "--"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    found: set[str] = set()
    for command in commands:
        try:
            result = subprocess.run(
                command, cwd=root, capture_output=True, text=True, timeout=60, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise WorkspaceError(f"git failed: {error}") from error
        if result.returncode != 0:
            raise WorkspaceError(f"git failed: {result.stderr.strip()[:200]}")
        found.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return sorted(path for path in found if not path.startswith("."))


def read_slices(workspace: Workspace, skills: Iterable[str]) -> dict[str, list[str]]:
    """Read the saved page slice of each skill.

    Args:
        workspace: The workspace.
        skills: Skill names.

    Returns:
        Skill → slice files, for skills that have a saved slice.
    """
    slices = {}
    for skill in skills:
        path = workspace.page_folder(skill) / "slice.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            slices[skill] = [str(item[0]) for item in data.get("files", [])]
    return slices


def find_drift(
    workspace: Workspace, graph: CodeGraph | None, changed: Iterable[str]
) -> DriftReport:
    """Decide which generated skills are stale.

    Args:
        workspace: The workspace.
        graph: The code graph (rebuilt after the change); None to use slices only.
        changed: Changed files.

    Returns:
        The report.
    """
    changed_list = sorted(set(changed))
    skills = [e.skill for e in workspace.read_routes().entries if e.has_form and not e.is_skipped]
    slices = read_slices(workspace, skills)
    affected = (
        find_affected_files(graph, changed_list, IMPACT_DEPTH) if graph else set(changed_list)
    )
    stale = find_stale_skills(slices, affected)
    unknown = sorted(skill for skill in skills if skill not in slices)
    return DriftReport(tuple(changed_list), tuple(stale), tuple(unknown))
