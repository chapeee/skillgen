"""Load hint packs: YAML data describing routers, folder routing and validators.

Hint packs are the only place framework knowledge lives; this module reads them
without knowing any framework.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillgen.errors import HintPackError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FolderPack:
    """A folder-routing convention.

    Attributes:
        id: Pack id.
        about: One-line description.
        roots: Folders to scan, relative to the repository.
        page_files: Glob patterns of file names that are pages.
        route_from: `folder` (route is the folder path) or `file` (the file path).
        index_names: File stems that stand for their folder (`index`).
        skip_segments: Regexes; matching path parts are dropped from the route.
        skip_files: Regexes; a matching path part means the file is not a page.
        params: Regexes with a `name` group; matching parts become `:name`.
        requires_any: Files marking a project root; the pack applies at every folder
            holding one, at any depth. Empty: the repository root only.
    """

    id: str
    about: str
    roots: tuple[str, ...]
    page_files: tuple[str, ...]
    route_from: str = "folder"
    index_names: tuple[str, ...] = ()
    skip_segments: tuple[re.Pattern[str], ...] = ()
    skip_files: tuple[re.Pattern[str], ...] = ()
    params: tuple[re.Pattern[str], ...] = ()
    requires_any: tuple[str, ...] = ()


@dataclass(frozen=True)
class RouterPack:
    """An ast-grep rule that finds route declarations.

    Attributes:
        id: Pack id.
        about: One-line description.
        language: ast-grep language name.
        rule: The ast-grep rule body.
        path_capture: Metavariable holding the route path.
        component_capture: Metavariable naming the page component, if any.
        globs: File globs the rule applies to.
        component_match: Regex with a `name` group applied to the captured component
            (for targets such as `registrations#new`); empty to use it as is.
        component_format: Format for the matched name, with `{name}` and `{pascal}`
            (such as `{pascal}Controller`); empty to use the name as is.
    """

    id: str
    about: str
    language: str
    rule: dict[str, Any]
    path_capture: str
    component_capture: str = ""
    globs: tuple[str, ...] = ()
    component_match: str = ""
    component_format: str = ""


@dataclass(frozen=True)
class HintPacks:
    """Every loaded pack, by kind.

    Attributes:
        folders: Folder-routing conventions.
        routers: Route-declaration rules.
        validators: Raw validator packs (used by analysis as hints).
    """

    folders: tuple[FolderPack, ...] = ()
    routers: tuple[RouterPack, ...] = ()
    validators: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _compile_all(patterns: Iterable[str], pack_id: str) -> tuple[re.Pattern[str], ...]:
    try:
        return tuple(re.compile(pattern) for pattern in patterns)
    except re.error as error:
        raise HintPackError(
            f"hint pack {pack_id!r} has a bad regular expression: {error}"
        ) from error


def _strings(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def parse_folder_pack(data: dict[str, Any]) -> FolderPack:
    """Build a folder pack from its YAML data.

    Args:
        data: The parsed YAML document.

    Returns:
        The pack.

    Raises:
        HintPackError: If required keys are missing or a regex is invalid.
    """
    pack_id = str(data.get("id", ""))
    if not pack_id or not data.get("roots") or not data.get("page_files"):
        raise HintPackError(f"folder pack {pack_id or '?'} needs id, roots and page_files")
    route_from = str(data.get("route_from", "folder"))
    if route_from not in ("folder", "file"):
        raise HintPackError(f"folder pack {pack_id}: route_from must be 'folder' or 'file'")
    return FolderPack(
        id=pack_id,
        about=str(data.get("about", "")),
        roots=_strings(data, "roots"),
        page_files=_strings(data, "page_files"),
        route_from=route_from,
        index_names=_strings(data, "index_names"),
        skip_segments=_compile_all(_strings(data, "skip_segments"), pack_id),
        skip_files=_compile_all(_strings(data, "skip_files"), pack_id),
        params=_compile_all(_strings(data, "params"), pack_id),
        requires_any=_strings(data, "requires_any"),
    )


def parse_router_pack(data: dict[str, Any]) -> RouterPack:
    """Build a router pack from its YAML data.

    Args:
        data: The parsed YAML document.

    Returns:
        The pack.

    Raises:
        HintPackError: If required keys are missing.
    """
    pack_id = str(data.get("id", ""))
    captures = data.get("captures", {})
    if not pack_id or not data.get("language") or not isinstance(data.get("rule"), dict):
        raise HintPackError(f"router pack {pack_id or '?'} needs id, language and rule")
    if not isinstance(captures, dict) or not captures.get("path"):
        raise HintPackError(f"router pack {pack_id} needs captures.path")
    return RouterPack(
        id=pack_id,
        about=str(data.get("about", "")),
        language=str(data["language"]),
        rule=dict(data["rule"]),
        path_capture=str(captures["path"]),
        component_capture=str(captures.get("component", "")),
        globs=_strings(data, "globs"),
        component_match=str(data.get("component_match", "")),
        component_format=str(data.get("component_format", "")),
    )


def read_pack_file(path: Path) -> dict[str, Any]:
    """Read one hint pack YAML file.

    Args:
        path: The file.

    Returns:
        The parsed document.

    Raises:
        HintPackError: If the file is not a YAML mapping.
    """
    # PyYAML costs about 80ms to import; it is loaded where YAML is actually read
    # or written, so a command that scans no routes does not pay for it.
    import yaml  # noqa: PLC0415 - import cost, see above

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise HintPackError(f"{path}: not valid YAML: {error}") from error
    if not isinstance(data, dict):
        raise HintPackError(f"{path}: a hint pack must be a YAML mapping")
    return data


def load_hint_packs(folders: Iterable[Path]) -> HintPacks:
    """Load every `*.yml` hint pack under the given folders.

    Later folders override packs with the same id, so a project can replace a
    shipped pack.

    Args:
        folders: Folders to read, such as the shipped `hintpacks/` and project extras.

    Returns:
        The loaded packs.

    Raises:
        HintPackError: If a pack is malformed.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for folder in folders:
        if not folder.is_dir():
            logger.warning("hint pack folder %s does not exist", folder)
            continue
        for path in sorted([*folder.rglob("*.yml"), *folder.rglob("*.yaml")]):
            data = read_pack_file(path)
            by_id[str(data.get("id", path.stem))] = data
    packs = list(by_id.values())
    return HintPacks(
        folders=tuple(parse_folder_pack(p) for p in packs if p.get("kind") == "folder"),
        routers=tuple(parse_router_pack(p) for p in packs if p.get("kind") == "router"),
        validators=tuple(p for p in packs if p.get("kind") == "validator"),
    )
