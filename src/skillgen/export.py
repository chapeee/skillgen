"""Export public skills: a folder, a zip, or one Claude Code or ChatGPT plugin per app.

Only skill folders and the index page leave the developer's machine. Every file is
scanned for secrets and personal data first, and `MANIFEST.sha256` records a hash of
every exported file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from skillgen import __version__
from skillgen.errors import ExportError
from skillgen.generate.bundle import build_bundle_files, read_frontmatter_value
from skillgen.routes.naming import MAX_NAME_LENGTH, is_valid_name
from skillgen.validate.scan import scan_files
from skillgen.validate.spec import check_skill_files, split_frontmatter
from skillgen.workspace import WORKSPACE_DIR, Workspace

logger = logging.getLogger(__name__)

MANIFEST = "MANIFEST.sha256"
INDEX_FILES = ("skills-index.html", "skills-index.json")
# The maintainer's decision: every exported plugin names this author (docs/decisions.md).
PLUGIN_AUTHOR = "chapeee"

# The portable Agent Plugins manifest that ChatGPT and Codex read from the plugin root.
CHATGPT_MANIFEST = "plugin.json"
AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
CHATGPT_ICON = "assets/icon.svg"
CHATGPT_CATEGORY = "Productivity"
CHATGPT_COMPATIBILITY_LEAD = "Built for ChatGPT with its built-in browser"
# One bundled skill is uploaded to whichever AI, so its line names none of them.
BUNDLE_COMPATIBILITY_LEAD = "Built for an AI with a built-in browser"
CHATGPT_TAGLINE = "Fills page forms in a browser"
# The directory listing cuts the display name and tagline at 30 characters.
MAX_LISTING_TEXT = 30
# A neutral form glyph; the plugin directory needs a square icon of at least 48 px.
CHATGPT_ICON_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#2f6feb"/>
  <rect x="14" y="15" width="36" height="9" rx="2" fill="#ffffff"/>
  <rect x="14" y="30" width="36" height="9" rx="2" fill="#ffffff"/>
  <rect x="14" y="45" width="18" height="6" rx="3" fill="#ffffff"/>
</svg>
"""


@dataclass(frozen=True)
class ExportResult:
    """What was exported.

    Attributes:
        path: The exported folder or zip file.
        skills: Skill names included.
        files: Number of files written.
    """

    path: Path
    skills: tuple[str, ...]
    files: int


def collect_export_files(workspace: Workspace, skills_root: Path, prefix: str) -> dict[str, str]:
    """Gather every file to export, keyed by its path inside the export.

    Args:
        workspace: The workspace.
        skills_root: The folder holding skill folders.
        prefix: Path inside the export where skill folders go (`skills/`).

    Returns:
        Relative path → text.

    Raises:
        ExportError: If there is nothing to export or a skill fails its checks.
    """
    if not skills_root.is_dir() or not any(p.is_dir() for p in skills_root.iterdir()):
        raise ExportError(f"no skills in {skills_root}; run generate first")
    files: dict[str, str] = {}
    for folder in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        skill_files = workspace.read_skill_files(folder)
        problems = check_skill_files(skill_files, folder.name)
        if problems:
            raise ExportError(f"{folder.name} fails its checks: {problems[0]}")
        files |= {f"{prefix}{folder.name}/{path}": text for path, text in skill_files.items()}
    for name in INDEX_FILES:
        if (workspace.root / name).is_file():
            files[name] = (workspace.root / name).read_text(encoding="utf-8")
    return files


def check_export_safety(files: dict[str, str]) -> None:
    """Refuse to export anything that looks like a secret or personal data.

    Args:
        files: Relative path → text.

    Raises:
        ExportError: If the scan finds anything.
    """
    findings = scan_files(files)
    if findings:
        first = findings[0]
        raise ExportError(
            f"export stopped: {len(findings)} finding(s); "
            f"first {first.path}:{first.line} looks like a {first.kind}"
        )


def build_manifest(files: dict[str, str]) -> str:
    """Build `MANIFEST.sha256` lines (`<sha256>  <path>`), sorted by path.

    Args:
        files: Relative path → text.

    Returns:
        The manifest text.
    """
    lines = [
        f"{hashlib.sha256(text.encode('utf-8')).hexdigest()}  {path}"
        for path, text in sorted(files.items())
    ]
    return "\n".join(lines) + "\n"


def build_plugin_manifest(name: str, app_name: str, skills: list[str]) -> str:
    """Build `.claude-plugin/plugin.json` for a plugin holding every skill.

    Args:
        name: Plugin name (a slug).
        app_name: The app's display name.
        skills: Skill names.

    Returns:
        The JSON text.
    """
    document = {
        "name": name,
        "version": __version__,
        "description": f"Page skills for {app_name or name}: "
        f"{len(skills)} form(s) Claude can fill.",
        "author": {"name": PLUGIN_AUTHOR},
    }
    return json.dumps(document, indent=2) + "\n"


def build_chatgpt_manifest(name: str, app_name: str, skills: list[str]) -> str:
    """Build the portable `plugin.json` for a skills-only ChatGPT plugin.

    Args:
        name: Plugin name (a slug).
        app_name: The app's display name.
        skills: Skill names.

    Returns:
        The JSON text.
    """
    title = app_name or name
    description = f"Page skills for {title}: {len(skills)} form(s) ChatGPT can fill in the browser."
    document = {
        "$schema": AGENT_PLUGINS_SCHEMA,
        "name": name,
        "version": __version__,
        "description": description,
        "author": {"name": PLUGIN_AUTHOR},
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": title[:MAX_LISTING_TEXT].rstrip(),
                    "shortDescription": CHATGPT_TAGLINE,
                    "longDescription": description,
                    "developerName": PLUGIN_AUTHOR,
                    "category": CHATGPT_CATEGORY,
                    "capabilities": [],
                    "composerIcon": f"./{CHATGPT_ICON}",
                    "logo": f"./{CHATGPT_ICON}",
                }
            }
        },
    }
    return json.dumps(document, indent=2) + "\n"


def check_chatgpt_names(plugin_name: str, skills: list[str]) -> None:
    """Refuse names ChatGPT would reject.

    Args:
        plugin_name: The plugin name.
        skills: Skill names.

    Raises:
        ExportError: If the plugin name breaks the naming rules, or a skill's
            `plugin:skill` identity is too long.
    """
    if not is_valid_name(plugin_name):
        raise ExportError(
            f"plugin name {plugin_name!r} must be 1–{MAX_NAME_LENGTH} lowercase letters, "
            "digits and single hyphens; pass --name"
        )
    # ChatGPT calls each skill `plugin:skill` and caps that identity like a skill name.
    too_long = [s for s in skills if len(f"{plugin_name}:{s}") > MAX_NAME_LENGTH]
    if too_long:
        raise ExportError(
            f"ChatGPT names each skill <plugin>:<skill> in at most {MAX_NAME_LENGTH} "
            f"characters, and {plugin_name}:{too_long[0]} is longer; pass a shorter --name "
            f"or rename the skill in {WORKSPACE_DIR}/routes.json"
        )


def write_export(files: dict[str, str], target: Path, *, as_zip: bool, root_name: str = "") -> Path:
    """Write files to a folder or a zip, with the manifest.

    Args:
        files: Relative path → text.
        target: Folder path (or zip path without suffix).
        as_zip: Write a zip file instead of a folder.
        root_name: The folder every zip entry sits in; the target's own name by
            default. A single skill's archive must name it after the skill, whatever
            the developer called the destination.

    Returns:
        The folder or zip written.
    """
    every = {**files, MANIFEST: build_manifest(files)}
    if as_zip:
        archive = target.with_suffix(".zip")
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path, text in sorted(every.items()):
                bundle.writestr(f"{root_name or target.name}/{path}", text)
        return archive
    if target.exists():
        shutil.rmtree(target)
    for path, text in every.items():
        destination = target / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        # The exact bytes MANIFEST.sha256 hashed, on every system.
        destination.write_text(text, encoding="utf-8", newline="\n")
    return target


def export_skills(
    workspace: Workspace,
    skills_root: Path,
    target: Path,
    *,
    as_zip: bool,
    plugin_name: str = "",
    app_name: str = "",
    one_skill_name: str = "",
) -> ExportResult:
    """Export every skill after checking and scanning it.

    Args:
        workspace: The workspace.
        skills_root: Folder holding skill folders.
        target: Destination folder (a `.zip` is written beside it with `as_zip`).
        as_zip: Write one zip file.
        plugin_name: When set, lay the export out as a Claude Code plugin of this name.
        app_name: The app's display name, for the plugin description.
        one_skill_name: When set, bundle every page into one skill of this name, so the
            export holds exactly one `SKILL.md`.

    Returns:
        What was exported.

    Raises:
        ExportError: If a skill fails its checks or the scan finds anything.
    """
    collected = collect_export_files(workspace, skills_root, "skills/")
    files, skills = _laid_out(collected, app_name, one_skill_name, inside_plugin=bool(plugin_name))
    check_export_safety(files)
    if plugin_name:
        files[".claude-plugin/plugin.json"] = build_plugin_manifest(plugin_name, app_name, skills)
    # Without a plugin manifest the archive's own folder is the skill folder, so an
    # upload that looks for `<skill-name>/SKILL.md` finds it.
    root = one_skill_name if one_skill_name and not plugin_name else ""
    written = write_export(files, target, as_zip=as_zip, root_name=root)
    logger.info("exported %d skill(s) to %s", len(skills), written)
    return ExportResult(written, tuple(skills), len(files) + 1)


def _laid_out(
    collected: dict[str, str], app_name: str, one_skill_name: str, *, inside_plugin: bool
) -> tuple[dict[str, str], list[str]]:
    """Lay collected files out as one folder per page, or bundled into one skill.

    Args:
        collected: What `collect_export_files` gathered.
        app_name: The app's display name.
        one_skill_name: The bundled skill's name; empty to keep one folder per page.
        inside_plugin: Put the bundled skill under `skills/`, as a plugin needs.

    Returns:
        (files to write, the page skill names).

    Raises:
        ExportError: If the bundled skill fails its checks.
    """
    if not one_skill_name:
        return collected, list_exported_skills(collected)
    pages = group_skill_files(collected)
    compatibility = build_bundle_compatibility(pages, BUNDLE_COMPATIBILITY_LEAD)
    bundle = build_bundle_files(one_skill_name, app_name, pages, compatibility)
    problems = check_skill_files(bundle, one_skill_name)
    if problems:
        raise ExportError(f"the bundled skill fails its checks: {problems[0]}")
    prefix = f"skills/{one_skill_name}/" if inside_plugin else ""
    return {f"{prefix}{path}": text for path, text in bundle.items()}, sorted(pages)


def export_chatgpt_plugin(
    workspace: Workspace,
    skills_root: Path,
    target: Path,
    *,
    as_zip: bool,
    plugin_name: str,
    app_name: str = "",
) -> ExportResult:
    """Export every page skill as one ChatGPT plugin holding a single skill.

    The layout is the portable one ChatGPT and Codex read: `plugin.json` at the root,
    the skill under `skills/<name>/` and the icon under `assets/`. Every page becomes
    a supporting file of that one skill, because an upload accepts exactly one
    `SKILL.md`. The index page stays out, since ChatGPT does not use it.

    Args:
        workspace: The workspace.
        skills_root: Folder holding skill folders.
        target: Destination folder (a `.zip` is written beside it with `as_zip`).
        as_zip: Write one zip file with the plugin as its single top-level folder.
        plugin_name: The plugin name, which also names the one skill.
        app_name: The app's display name, for the listing.

    Returns:
        What was exported.

    Raises:
        ExportError: If a name breaks ChatGPT's rules, a skill fails its checks, or
            the scan finds anything.
    """
    collected = collect_export_files(workspace, skills_root, "skills/")
    pages = group_skill_files(collected)
    check_chatgpt_names(plugin_name, [plugin_name])
    compatibility = build_bundle_compatibility(pages, CHATGPT_COMPATIBILITY_LEAD)
    bundle = build_bundle_files(plugin_name, app_name, pages, compatibility)
    files = {f"skills/{plugin_name}/{path}": text for path, text in bundle.items()}
    check_export_safety(files)
    problems = check_skill_files(bundle, plugin_name)
    if problems:
        raise ExportError(f"the bundled skill fails its checks: {problems[0]}")
    files[CHATGPT_MANIFEST] = build_chatgpt_manifest(plugin_name, app_name, sorted(pages))
    files[CHATGPT_ICON] = CHATGPT_ICON_SVG
    written = write_export(files, target, as_zip=as_zip)
    logger.info(
        "exported %d page(s) as the ChatGPT plugin %s to %s", len(pages), plugin_name, written
    )
    return ExportResult(written, tuple(sorted(pages)), len(files) + 1)


def group_skill_files(files: Mapping[str, str]) -> dict[str, dict[str, str]]:
    """Group collected export files by the skill folder they came from.

    Args:
        files: Relative path → text, with skill folders under `skills/`.

    Returns:
        Skill name → its files, by path inside its own folder.
    """
    pages: dict[str, dict[str, str]] = {}
    for path, text in files.items():
        if not path.startswith("skills/"):
            continue
        skill, _, inside = path[len("skills/") :].partition("/")
        pages.setdefault(skill, {})[inside] = text
    return pages


def build_bundle_compatibility(pages: Mapping[str, Mapping[str, str]], lead: str) -> str:
    """Write the bundled skill's compatibility line, naming the app it needs.

    Args:
        pages: Each page skill's files, by skill name.
        lead: What the line opens with, naming the AI the export is for.

    Returns:
        The compatibility line.
    """
    urls = {
        read_frontmatter_value(split_frontmatter(files["SKILL.md"])[0], "app-url")
        for files in pages.values()
        if "SKILL.md" in files
    }
    known = sorted(url for url in urls if url)
    where = f"needs access to {known[0]}" if len(known) == 1 else "needs access to the app"
    return f"{lead}; {where}."


def list_exported_skills(files: dict[str, str]) -> list[str]:
    """List the skill names among export files.

    Args:
        files: Relative path → text, with skill folders under `skills/`.

    Returns:
        Skill names, sorted.
    """
    return sorted({path.split("/")[1] for path in files if path.startswith("skills/")})
