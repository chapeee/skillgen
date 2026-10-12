"""Find route declarations with ast-grep router packs (optional `astgrep` extra).

ast-grep runs as a subprocess. When it is not installed this source finds nothing
and discovery carries on with the others.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from skillgen.model.route import RouteCandidate
from skillgen.routes.folders import SKIPPED_FOLDERS
from skillgen.routes.hintpacks import RouterPack
from skillgen.routes.paths import normalize_route, strip_quotes

logger = logging.getLogger(__name__)

AST_GREP_NAMES = ("ast-grep", "sg")
TIMEOUT_SECONDS = 120
# Route declarations are never taken from credentials or generated/dependency trees.
# ``secrets`` is kept local to the code scanner because folder routing may legitimately
# inspect a project directory with that name for a different purpose.
ROUTE_SCAN_SKIPPED_FOLDERS = SKIPPED_FOLDERS | {"secrets"}

# Maps a component name and the declaring file to the page's entry file, if known.
ComponentResolver = Callable[[str, str], str | None]


def find_ast_grep() -> str | None:
    """Return the ast-grep executable, or None when it is not installed.

    Looks next to the running Python first: `uv tool install` and `pipx` put the
    `astgrep` extra's binary in skillgen's own environment, which is not on PATH.
    """
    environment_bin = str(Path(sys.executable).parent)
    for name in AST_GREP_NAMES:
        found = shutil.which(name, path=environment_bin) or shutil.which(name)
        # `sg` is also a Linux group tool; only accept it when it is ast-grep.
        if found and (name == "ast-grep" or _is_ast_grep(found)):
            return found
    return None


def _is_ast_grep(executable: str) -> bool:
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "ast-grep" in result.stdout


def run_ast_grep(
    executable: str,
    pack: RouterPack,
    repository: Path,
    excluded: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Run one router pack over a repository.

    Args:
        executable: The ast-grep binary.
        pack: The router pack.
        repository: Where to scan.
        excluded: Repository-relative generated paths to leave out.

    Returns:
        ast-grep's JSON matches; empty when the run fails.
    """
    # PyYAML costs about 80ms to import; it is loaded where YAML is actually read
    # or written, so a command that scans no routes does not pay for it.
    import yaml  # noqa: PLC0415 - import cost, see above

    rule: dict[str, Any] = {"id": pack.id, "language": pack.language, "rule": pack.rule}
    if pack.globs:
        rule["files"] = list(pack.globs)
    ignored = tuple(_normalise_path(item) for item in excluded)
    with tempfile.TemporaryDirectory() as folder:
        rule_path = Path(folder) / "rule.yml"
        rule_path.write_text(yaml.safe_dump(rule), encoding="utf-8")
        command = [executable, "scan", "--rule", str(rule_path), "--json=compact"]
        # A project without .gitignore would otherwise be searched inside its
        # dependencies, where bundled code looks like route declarations.
        for name in sorted(ROUTE_SCAN_SKIPPED_FOLDERS):
            command += ["--globs", f"!**/{name}/**"]
        command += ["--globs", "!.*", "--globs", "!**/.*"]
        # Applicability is checked against this same inventory.  The explicit globs
        # also keep generated files out of ast-grep's result when a repository has no
        # ignore file of its own.
        for path in ignored:
            command += ["--globs", f"!{path}", "--globs", f"!{path}/**"]
        command.append(".")
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=repository,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            logger.warning(
                "ast-grep pack %s failed after %.2fs: %s",
                pack.id,
                time.monotonic() - started,
                error,
            )
            return []
    if result.returncode not in (0, 1) or not result.stdout.strip():
        if result.stderr.strip():
            logger.warning("ast-grep pack %s: %s", pack.id, result.stderr.strip()[:300])
        logger.info(
            "ast-grep pack %s finished in %.2fs with no matches",
            pack.id,
            time.monotonic() - started,
        )
        return []
    matches: list[dict[str, Any]] = json.loads(result.stdout)
    logger.info(
        "ast-grep pack %s finished in %.2fs with %d match(es)",
        pack.id,
        time.monotonic() - started,
        len(matches),
    )
    return [match for match in matches if _is_allowed_match(match, repository, ignored)]


def _is_allowed_match(match: dict[str, Any], repository: Path, excluded: tuple[str, ...]) -> bool:
    """Tell whether an ast-grep result belongs to scannable repository source."""
    file_name = str(match.get("file", ""))
    if not file_name:
        return False
    # ast-grep normally returns relative paths, but checking the resolved path here
    # prevents a symlink or a crafted absolute result from escaping the repository.
    candidate = Path(file_name)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(repository.resolve()).as_posix()
        except (OSError, RuntimeError, ValueError):
            return False
    else:
        relative = _normalise_path(file_name)
        candidate = repository / candidate
    if is_in_skipped_folder(relative) or _is_excluded(relative, excluded):
        return False
    try:
        candidate.resolve().relative_to(repository.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return not candidate.is_symlink()


def is_in_skipped_folder(file: str) -> bool:
    """Whether a path lies in dependencies or build output, where routes are never declared.

    Args:
        file: A path relative to the repository, with either kind of slash.

    Returns:
        True when any folder on the path is skipped.
    """
    parts = file.replace("\\", "/").split("/")
    return bool(ROUTE_SCAN_SKIPPED_FOLDERS.intersection(parts)) or any(
        part.startswith(".") and part not in (".", "..") for part in parts
    )


def shape_component(raw: str, pack: RouterPack) -> str:
    """Apply a pack's component regex and format to a captured component.

    Args:
        raw: The captured text, such as `"registrations#new"`.
        pack: The router pack.

    Returns:
        The component name to resolve, such as `RegistrationsController`.
    """
    name = raw
    if pack.component_match:
        found = re.search(pack.component_match, raw)
        if not found:
            return raw
        name = found.group("name")
    if not pack.component_format:
        return name
    pascal = "".join(
        part[:1].upper() + part[1:] for part in re.split(r"[_/\-]", name.split("/")[-1]) if part
    )
    return pack.component_format.format(name=name, pascal=pascal)


def read_match(match: dict[str, Any], pack: RouterPack) -> tuple[str, str, str] | None:
    """Pull the route, component name and file out of one ast-grep match.

    Args:
        match: One JSON match.
        pack: The pack that produced it.

    Returns:
        (route, component, file), or None when the path is not a literal route.
    """
    captured = match.get("metaVariables", {}).get("single", {})
    raw_path = str(captured.get(pack.path_capture, {}).get("text", ""))
    path = strip_quotes(raw_path)
    # Dynamic paths (variables, template strings) cannot be routes we can name.
    if (
        not path
        or any(mark in path for mark in ("${", "+"))
        or (raw_path == path and not path.startswith("/"))
    ):
        return None
    component = (
        str(captured.get(pack.component_capture, {}).get("text", ""))
        if pack.component_capture
        else ""
    )
    return (
        normalize_route(path),
        shape_component(component, pack) if component else "",
        # ast-grep prints Windows paths with backslashes; routes.json always uses `/`.
        Path(str(match.get("file", ""))).as_posix() if match.get("file") else "",
    )


def find_declared_routes(
    repository: Path,
    packs: Iterable[RouterPack],
    resolve_component: ComponentResolver | None = None,
    excluded: Iterable[str] = (),
) -> list[RouteCandidate]:
    """Find routes declared in code, using every router pack.

    Args:
        repository: The repository root.
        packs: Router packs to run.
        resolve_component: Turns a component name into its file, usually through the
            code graph; when absent, the declaring file is the entry file.
        excluded: Generated repository paths that must not be scanned.

    Returns:
        One candidate per declaration.
    """
    executable = find_ast_grep()
    if executable is None:
        logger.info("ast-grep is not installed; skipping router hint packs")
        return []
    applicable_files = repository_files(repository, excluded)
    candidates = []
    for pack in packs:
        if not pack_applies_to_files(pack, applicable_files):
            logger.info("router pack %s has no matching files; skipping ast-grep", pack.id)
            continue
        for match in run_ast_grep(executable, pack, repository, excluded):
            found = read_match(match, pack)
            if found is None:
                continue
            route, component, declared_in = found
            entry = (
                resolve_component(component, declared_in)
                if resolve_component and component
                else None
            )
            # The declaring file usually lists every route of the app, so a slice grown
            # from it would hold every page; it is the entry only when nothing better is.
            entry_files = (entry,) if entry else (declared_in,)
            candidates.append(RouteCandidate(route, f"router:{pack.id}", entry_files))
    logger.info("router packs found %d route(s)", len(candidates))
    return candidates


def repository_files(repository: Path, excluded: Iterable[str] = ()) -> tuple[str, ...]:
    """List non-skipped, non-generated files once for applicability checks.

    Args:
        repository: Repository root.
        excluded: Repository-relative generated paths to ignore.

    Returns:
        Relative POSIX file paths.
    """
    ignored = tuple(_normalise_path(item) for item in excluded)
    files: list[str] = []
    for directory, directories, names in os.walk(repository, topdown=True, followlinks=False):
        # Pruning before descent keeps dependency trees and hidden caches out of both
        # the inventory and the potentially expensive route scan.  Symlinked folders
        # are removed explicitly because callers must never scan outside the root.
        directory_path = Path(directory)
        directories[:] = sorted(
            name
            for name in directories
            if name not in ROUTE_SCAN_SKIPPED_FOLDERS
            and not name.startswith(".")
            and not (directory_path / name).is_symlink()
            and not _is_excluded(
                (directory_path / name).relative_to(repository).as_posix(), ignored
            )
        )
        for name in sorted(names):
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(repository).as_posix()
            if not is_in_skipped_folder(relative) and not _is_excluded(relative, ignored):
                files.append(relative)
    return tuple(files)


def pack_applies_to_files(pack: RouterPack, files: Iterable[str]) -> bool:
    """Tell whether a router pack has at least one file it could scan.

    Only the small, unambiguous subset understood here is used as a shortcut.  A
    pattern with globset features we do not model is treated as applicable so a
    route is never lost because an optimization misunderstood the pattern.
    """
    if not pack.globs:
        return True
    compiled = tuple(_compile_supported_glob(pattern) for pattern in pack.globs)
    if any(pattern is None for pattern in compiled):
        return True
    normalized_files = tuple(_normalise_path(file) for file in files)
    return any(
        regex.fullmatch(file) is not None
        for regex in compiled
        for file in normalized_files
        if regex is not None
    )


def _compile_supported_glob(pattern: str) -> re.Pattern[str] | None:
    """Compile a conservative repository glob, or return None when uncertain.

    The globset syntax accepted by ast-grep is broader than ``PurePath.match``.
    In particular, ``**/name`` matches both a root file and a nested file.  This
    compiler handles literal path segments, ``*``, ``?`` and whole-directory
    ``**`` segments; braces, negation, character classes and other extensions are
    deliberately left to ast-grep.
    """
    if "\\" in pattern:
        return None
    normalized = pattern
    if (
        not normalized
        or normalized.startswith("!")
        or normalized.startswith("/")
        or any(mark in normalized for mark in ("!", "{", "}", "[", "]", "(", ")", "|"))
    ):
        return None
    parts = normalized.split("/")
    if any("**" in part and part != "**" for part in parts):
        return None
    if any(part == "" for part in parts):
        return None
    if any(parts[index] == parts[index + 1] == "**" for index in range(len(parts) - 1)):
        return None
    expression = _glob_expression(parts)
    # A slashless globset pattern applies to a basename at any depth.
    if len(parts) == 1:
        expression = "^" + r"(?:[^/]+/)*" + expression[1:]
    return re.compile(expression)


def _glob_expression(parts: list[str]) -> str:
    """Build the regex body for supported glob path segments."""
    expression: list[str] = ["^"]
    for index, part in enumerate(parts):
        if part == "**":
            if index and parts[index - 1] != "**":
                expression.append("/")
            if index == len(parts) - 1:
                expression.append(r"(?:[^/]+(?:/|$))*")
            else:
                expression.append(r"(?:[^/]+/)*")
            continue
        if index and parts[index - 1] != "**":
            expression.append("/")
        expression.append(_glob_segment_expression(part))
    expression.append("$")
    return "".join(expression)


def _glob_segment_expression(segment: str) -> str:
    """Build a regex body for a path segment containing ``*`` and ``?``."""
    output: list[str] = []
    for character in segment:
        if character == "*":
            output.append("[^/]*")
        elif character == "?":
            output.append("[^/]")
        else:
            output.append(re.escape(character))
    return "".join(output)


def _normalise_path(path: str) -> str:
    """Normalize one repository-relative path for generated-output checks."""
    return PurePosixPath(path.replace("\\", "/")).as_posix()


def _is_excluded(path: str, excluded: tuple[str, ...]) -> bool:
    """Tell whether a repository-relative path belongs to generated output."""
    return any(path == item or path.startswith(f"{item}/") for item in excluded)
