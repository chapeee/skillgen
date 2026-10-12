"""Find routes from folder-routing conventions described by folder hint packs."""

from __future__ import annotations

import fnmatch
import logging
import os
from collections.abc import Iterable
from pathlib import Path

from skillgen.model.route import RouteCandidate
from skillgen.routes.hintpacks import FolderPack

logger = logging.getLogger(__name__)

# Folders that never hold an app's own pages.
SKIPPED_FOLDERS = frozenset({"node_modules", ".git", "dist", "build", ".next", ".nuxt", "vendor"})


def build_folder_route(parts: list[str], pack: FolderPack) -> str | None:
    """Turn the path parts of a page file below a pack root into a route.

    Args:
        parts: Path parts relative to the root, ending with the file name.
        pack: The convention.

    Returns:
        The route, or None when the file is not a page under this convention.
    """
    *folders, file_name = parts
    stem = file_name.split(".", 1)[0]
    segments = folders if pack.route_from == "folder" else [*folders, stem]
    if pack.route_from == "file" and stem in pack.index_names:
        segments = folders
    if any(skip.search(part) for part in segments for skip in pack.skip_files):
        return None
    if pack.route_from == "file" and any(skip.search(stem) for skip in pack.skip_files):
        return None
    route_parts = []
    for segment in segments:
        if any(skip.search(segment) for skip in pack.skip_segments):
            continue
        param = next((m for m in (p.match(segment) for p in pack.params) if m), None)
        route_parts.append(f":{param.group('name')}" if param else segment)
    return "/" + "/".join(route_parts)


def _is_page_file(name: str, pack: FolderPack) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in pack.page_files)


def _walk_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not SKIPPED_FOLDERS.intersection(path.relative_to(root).parts):
            yield path


def list_folders(repository: Path) -> list[tuple[Path, frozenset[str]]]:
    """List every folder of the repository with its file names, skipping build output.

    Args:
        repository: The repository root.

    Returns:
        (folder, names of the files directly in it), top folder first.
    """
    found: list[tuple[Path, frozenset[str]]] = []
    for directory, folders, files in os.walk(repository):
        # Pruned in place, so os.walk never descends into dependencies or build output.
        folders[:] = sorted(
            name for name in folders if name not in SKIPPED_FOLDERS and not name.startswith(".")
        )
        found.append((Path(directory), frozenset(files)))
    return found


def find_project_roots(
    repository: Path, pack: FolderPack, folders: list[tuple[Path, frozenset[str]]]
) -> list[Path]:
    """Find the project roots a folder pack applies at.

    A pack with marker files applies at every folder holding one of them, at any depth,
    so an app two folders down in a monorepo is found like one at the top. A pack
    without markers applies at the repository root only.

    Args:
        repository: The repository root.
        pack: The convention.
        folders: Every folder with its file names, from `list_folders`.

    Returns:
        The project roots, top first.
    """
    if not pack.requires_any:
        return [repository]
    markers = set(pack.requires_any)
    return [folder for folder, names in folders if markers & names]


def find_folder_routes(repository: Path, packs: Iterable[FolderPack]) -> list[RouteCandidate]:
    """Find routes in folder-routed trees.

    Args:
        repository: The repository root.
        packs: Folder conventions to try.

    Returns:
        One candidate per page file, with that file as the entry file.
    """
    candidates: list[RouteCandidate] = []
    folders = list_folders(repository)
    for pack in packs:
        for project in find_project_roots(repository, pack, folders):
            for root_name in pack.roots:
                root = project / root_name
                if root.is_dir():
                    candidates += _find_pages(repository, root, pack)
    logger.info("folder packs found %d route(s)", len(candidates))
    return candidates


def _find_pages(repository: Path, root: Path, pack: FolderPack) -> list[RouteCandidate]:
    found: list[RouteCandidate] = []
    for path in _walk_files(root):
        if not _is_page_file(path.name, pack):
            continue
        route = build_folder_route(list(path.relative_to(root).parts), pack)
        if route is not None:
            relative = path.relative_to(repository).as_posix()
            found.append(RouteCandidate(route, f"folder:{pack.id}", (relative,)))
    return found
