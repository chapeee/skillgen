"""Bundle several page skills into one skill folder with a single `SKILL.md`.

Some AIs accept exactly one `SKILL.md` per upload, so one skill per page cannot be
uploaded together. This builds one entry-point `SKILL.md` that lists every page and
says which file to read for it; each page's own text and scripts become supporting
files beside it. Nothing is rewritten but the paths the text points at.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from skillgen import TOOL_NAME, __version__
from skillgen.routes.naming import MAX_DESCRIPTION_LENGTH
from skillgen.validate.spec import split_frontmatter

# Where a bundled page's former `SKILL.md` body goes, under its own folder.
PAGE_FILE = "page.md"
PAGE_FOLDER = "references"
SCRIPT_FOLDER = "scripts"
# Developer test files are not skill content; they stay out of a bundle.
DROPPED_FOLDERS = ("evals/",)
# How much of a page's description the entry point repeats, so it stays small.
MAX_SUMMARY_LENGTH = 160

_HEADING = re.compile(r"^# (.*?)(?: — (/\S*))?$", re.MULTILINE)
_SUPPORT_PATH = re.compile(r"\b(scripts|references)/([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass(frozen=True)
class PageEntry:
    """One page in a bundle.

    Attributes:
        skill: The page skill's name, which names its folder inside the bundle.
        title: The page title, as its own `SKILL.md` headed it.
        route: The route, such as `/apply`.
        summary: What the page is for, short enough for the entry point's table.
    """

    skill: str
    title: str
    route: str
    summary: str


def read_frontmatter_value(frontmatter: str, key: str) -> str:
    """Read one top-level string value out of raw frontmatter text.

    Args:
        frontmatter: The frontmatter text, without its fences.
        key: The key to read.

    Returns:
        The value with any quotes stripped; empty when the key is absent.
    """
    # Nested keys (`metadata: route:`) are read the same way; only the value matters.
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+)$", frontmatter, re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip().strip('"')


def summarize_description(description: str, limit: int = MAX_SUMMARY_LENGTH) -> str:
    """Keep the part of a page description that says what is on the page.

    A page's description opens by naming the form and its route, which the table
    already has its own columns for, and closes with when to use the skill. What is
    left in the middle is the list of what the page covers.

    Args:
        description: The page skill's description.
        limit: Most characters to keep.

    Returns:
        The shortened summary.
    """
    middle = description.split(": ", 1)[-1].split(". Use when asked", 1)[0].rstrip(".")
    if len(middle) <= limit:
        return middle
    return middle[:limit].rsplit(" ", 1)[0] + "…"


def describe_page(skill: str, skill_md: str) -> PageEntry:
    """Read a page skill's own `SKILL.md` for the entry point's table.

    Args:
        skill: The page skill's name.
        skill_md: Its `SKILL.md` text.

    Returns:
        The page's entry.
    """
    frontmatter, body = split_frontmatter(skill_md)
    heading = _HEADING.search(body)
    title = heading.group(1).strip() if heading else skill
    route = (heading.group(2) or "") if heading else ""
    route = route or read_frontmatter_value(frontmatter, "route")
    summary = summarize_description(read_frontmatter_value(frontmatter, "description"))
    return PageEntry(skill, title, route, summary)


def retarget_support_paths(text: str, skill: str) -> str:
    """Point a page's own file references at its folder inside the bundle.

    Args:
        text: Text that may name `scripts/…` or `references/…` files.
        skill: The page skill's name.

    Returns:
        The text with each of those paths moved under the page's folder.
    """
    return _SUPPORT_PATH.sub(rf"\1/{skill}/\2", text)


def build_page_files(skill: str, files: Mapping[str, str]) -> dict[str, str]:
    """Lay one page skill's files out inside a bundle.

    Args:
        skill: The page skill's name.
        files: Its files, by path relative to its own folder.

    Returns:
        The page's files, by path relative to the bundle's folder.
    """
    out: dict[str, str] = {}
    for path, text in files.items():
        if path.startswith(DROPPED_FOLDERS):
            continue
        moved = retarget_support_paths(text, skill)
        if path == "SKILL.md":
            out[f"{PAGE_FOLDER}/{skill}/{PAGE_FILE}"] = split_frontmatter(moved)[1].lstrip("\n")
        elif path.startswith(f"{SCRIPT_FOLDER}/"):
            out[f"{SCRIPT_FOLDER}/{skill}/{path.split('/', 1)[1]}"] = moved
        else:
            out[f"{PAGE_FOLDER}/{skill}/{path.split('/', 1)[-1]}"] = moved
    return out


def build_bundle_description(app_name: str, pages: list[PageEntry]) -> str:
    """Write the entry point's description, naming as many pages as fit.

    Args:
        app_name: The app's display name.
        pages: The pages in the bundle.

    Returns:
        A description under 300 characters.
    """
    where = app_name or "this app"
    named = [f"{page.title} ({page.route})" if page.route else page.title for page in pages]
    while True:
        listed = ", ".join(named)
        more = f" and {len(pages) - len(named)} more" if len(named) < len(pages) else ""
        text = (
            f"Fills forms in {where}: {listed}{more}. Use when asked to fill in, complete "
            "or submit one of these forms."
        )
        if len(text) <= MAX_DESCRIPTION_LENGTH or len(named) <= 1:
            return text
        named.pop()


def render_page_table(pages: list[PageEntry]) -> list[str]:
    """Render the table that sends the reader to one page's file.

    Args:
        pages: The pages in the bundle.

    Returns:
        Markdown lines.
    """
    lines = ["| Form | Route | What it is | Read this file |", "|---|---|---|---|"]
    for page in pages:
        cells = [
            page.title,
            f"`{page.route}`" if page.route else "",
            page.summary,
            f"`{PAGE_FOLDER}/{page.skill}/{PAGE_FILE}`",
        ]
        lines.append("| " + " | ".join(" ".join(cell.split()) for cell in cells) + " |")
    return lines


def build_entry_skill_md(
    name: str, app_name: str, pages: list[PageEntry], compatibility: str = ""
) -> str:
    """Render the bundle's single `SKILL.md`: what each page is, and which file to read.

    Args:
        name: The bundle's skill name, which is also its folder name.
        app_name: The app's display name.
        pages: The pages in the bundle.
        compatibility: The compatibility line; left out when empty.

    Returns:
        The file content, ending with a newline.
    """
    description = build_bundle_description(app_name, pages)
    lines = ["---", f"name: {name}", f'description: "{description}"']
    if compatibility:
        lines.append(f'compatibility: "{compatibility}"')
    lines += [
        "metadata:",
        f'  generator: "{TOOL_NAME} {__version__}"',
        f'  pages: "{len(pages)}"',
        "---",
        "",
        f"# {app_name or name} forms",
        "",
        "One file per form. Read only the one form the user asks for: it carries that "
        "page's fields, how to fill them and how to submit, and is written to be followed "
        "on its own.",
        "",
        "## Forms",
        *render_page_table(pages),
        "",
        "## How to use",
        "1. Match the user's request to one row above. If none fits, say so and stop; never "
        "guess a form.",
        "2. Read that row's file and follow it from there.",
        "3. Read nothing else first: no other form's file, and not the page in the browser.",
        "",
    ]
    return "\n".join(lines)


def build_bundle_files(
    name: str,
    app_name: str,
    skills: Mapping[str, Mapping[str, str]],
    compatibility: str = "",
) -> dict[str, str]:
    """Bundle several page skills into the files of one skill folder.

    Args:
        name: The bundle's skill name, which is also its folder name.
        app_name: The app's display name.
        skills: Each page skill's files, by skill name, then by path inside its folder.
        compatibility: The compatibility line for the bundle's `SKILL.md`.

    Returns:
        The bundle's files, by path relative to its folder, with exactly one `SKILL.md`.
    """
    pages = [describe_page(skill, files["SKILL.md"]) for skill, files in sorted(skills.items())]
    out = {"SKILL.md": build_entry_skill_md(name, app_name, pages, compatibility)}
    for skill, files in sorted(skills.items()):
        out |= build_page_files(skill, files)
    return out
