"""The `.skillgen/` workspace: where every internal file lives, and reading and writing them.

Layout (spec section 13):

    .skillgen/
      config.json  routes.json  questions.json
      pages/<skill>/page.json  analysis.json  slice.json  evidence.jsonl  probe/
      rules/global.md
      secrets/            login state for probing; never committed or exported
      cache/              code graph and other caches
    skills/<skill>/       public output, one folder per route
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skillgen import TOOL_NAME
from skillgen.config import Settings, settings_from_dict, settings_to_dict
from skillgen.errors import SchemaError, WorkspaceError
from skillgen.model.facts import Evidence
from skillgen.model.page import PageModel
from skillgen.model.route import (
    Question,
    RouteTable,
    question_from_dict,
    question_to_dict,
    route_entry_from_dict,
    route_entry_to_dict,
)
from skillgen.model.serialize import page_from_dict, page_to_dict
from skillgen.schema import validate_document

logger = logging.getLogger(__name__)

WORKSPACE_DIR = f".{TOOL_NAME}"
GITIGNORE_LINES = ("secrets/", "cache/", "logs/")


def write_text_atomically(path: Path, text: str) -> None:
    """Write a file so readers never see it half-written.

    Args:
        path: Destination.
        text: Content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    # The same bytes on every system: text mode on Windows would turn each "\n" into
    # "\r\n", so a skill would differ by platform and fail its export manifest.
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    Path(temporary).replace(path)


def write_json(path: Path, data: object) -> None:
    """Write pretty JSON atomically.

    Args:
        path: Destination.
        data: JSON-ready data.
    """
    write_text_atomically(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    """Read a JSON file.

    Args:
        path: The file.

    Returns:
        The parsed document.

    Raises:
        WorkspaceError: If the file is missing or not JSON.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise WorkspaceError(f"{path} does not exist") from error
    except json.JSONDecodeError as error:
        raise WorkspaceError(f"{path} is not valid JSON: {error}") from error


def find_workspace_root(start: Path) -> Path | None:
    """Walk up from a folder to the first one holding a `.skillgen/` workspace.

    Args:
        start: Where to start.

    Returns:
        The repository root, or None when there is no workspace above `start`.
    """
    for folder in (start.resolve(), *start.resolve().parents):
        if (folder / WORKSPACE_DIR / "config.json").is_file():
            return folder
    return None


@dataclass(frozen=True)
class Workspace:
    """Paths and file access for one repository's workspace.

    Attributes:
        root: The repository root (the folder that holds `.skillgen/`).
    """

    root: Path

    @property
    def folder(self) -> Path:
        """The `.skillgen/` folder."""
        return self.root / WORKSPACE_DIR

    @property
    def config_path(self) -> Path:
        """Path of `config.json`."""
        return self.folder / "config.json"

    @property
    def routes_path(self) -> Path:
        """Path of `routes.json`."""
        return self.folder / "routes.json"

    @property
    def questions_path(self) -> Path:
        """Path of `questions.json`."""
        return self.folder / "questions.json"

    @property
    def global_rules_path(self) -> Path:
        """Path of `rules/global.md`."""
        return self.folder / "rules" / "global.md"

    @property
    def cache_folder(self) -> Path:
        """The cache folder (code graph and similar)."""
        return self.folder / "cache"

    @property
    def secrets_folder(self) -> Path:
        """The secrets folder (probe login state)."""
        return self.folder / "secrets"

    def page_folder(self, skill: str) -> Path:
        """Return the internal folder of one page."""
        return self.folder / "pages" / skill

    def skills_folder(self, settings: Settings) -> Path:
        """Return the folder that holds public skill folders."""
        return self.root / settings.skills_dir

    def exists(self) -> bool:
        """Tell whether the workspace has been initialised."""
        return self.config_path.is_file()

    def create(self, settings: Settings) -> None:
        """Create the workspace folders, config and a `.gitignore` for secrets.

        Args:
            settings: Initial settings.
        """
        for folder in (
            self.folder / "pages",
            self.folder / "rules",
            self.secrets_folder,
            self.cache_folder,
        ):
            folder.mkdir(parents=True, exist_ok=True)
        write_text_atomically(self.folder / ".gitignore", "\n".join(GITIGNORE_LINES) + "\n")
        if not self.global_rules_path.exists():
            write_text_atomically(
                self.global_rules_path,
                "# Rules for all pages\n\nOne rule per line starting with `- `. "
                "They are copied into every skill.\n",
            )
        self.write_settings(settings)

    def read_settings(self) -> Settings:
        """Read `config.json`.

        Returns:
            The settings.

        Raises:
            WorkspaceError: If the workspace does not exist.
        """
        if not self.exists():
            raise WorkspaceError(f"no workspace at {self.folder}; run `{TOOL_NAME} init` first")
        return settings_from_dict(read_json(self.config_path))

    def write_settings(self, settings: Settings) -> None:
        """Write `config.json`."""
        write_json(self.config_path, settings_to_dict(settings))

    def read_routes(self) -> RouteTable:
        """Read `routes.json`; an empty table when it does not exist yet."""
        if not self.routes_path.exists():
            return RouteTable()
        data = read_json(self.routes_path)
        return RouteTable(tuple(route_entry_from_dict(item) for item in data.get("routes", [])))

    def write_routes(self, table: RouteTable) -> None:
        """Write `routes.json`."""
        write_json(self.routes_path, {"routes": [route_entry_to_dict(e) for e in table.entries]})

    def read_questions(self) -> list[Question]:
        """Read `questions.json`; empty when it does not exist yet."""
        if not self.questions_path.exists():
            return []
        return [
            question_from_dict(item) for item in read_json(self.questions_path).get("questions", [])
        ]

    def write_questions(self, questions: Iterable[Question]) -> None:
        """Write `questions.json`."""
        write_json(self.questions_path, {"questions": [question_to_dict(q) for q in questions]})

    def read_global_rules(self) -> tuple[str, ...]:
        """Read the bullet lines of `rules/global.md`."""
        if not self.global_rules_path.exists():
            return ()
        lines = self.global_rules_path.read_text(encoding="utf-8").splitlines()
        return tuple(line.strip()[2:].strip() for line in lines if line.strip().startswith("- "))

    def read_page(self, skill: str) -> PageModel | None:
        """Read a page's `page.json`, validating it; None when it does not exist.

        Raises:
            WorkspaceError: If the file does not match the page schema.
        """
        path = self.page_folder(skill) / "page.json"
        if not path.exists():
            return None
        data = read_json(path)
        try:
            validate_document(data, "page")
        except SchemaError as error:
            raise WorkspaceError(f"{path}: {error}") from error
        return page_from_dict(data)

    def write_page(self, page: PageModel) -> Path:
        """Write a page's `page.json` and return its path."""
        path = self.page_folder(page.skill) / "page.json"
        write_json(path, page_to_dict(page))
        return path

    def write_evidence(self, skill: str, evidence: Iterable[Evidence]) -> None:
        """Replace a page's `evidence.jsonl`."""
        lines = [
            json.dumps(
                {
                    "subject": e.subject,
                    "source": e.source.value,
                    "location": e.location,
                    "detail": e.detail,
                }
            )
            for e in evidence
        ]
        write_text_atomically(
            self.page_folder(skill) / "evidence.jsonl", "\n".join(lines) + "\n" if lines else ""
        )

    def read_skill_files(self, folder: Path) -> dict[str, str]:
        """Read every text file of a skill folder by relative path."""
        if not folder.is_dir():
            return {}
        return {
            path.relative_to(folder).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(folder.rglob("*"))
            if path.is_file()
        }

    def write_skill_files(self, folder: Path, files: Mapping[str, str]) -> None:
        """Write a skill folder, removing generated files that no longer exist.

        Only files skillgen generates are removed; anything else a developer added stays.
        """
        generated = {
            "SKILL.md",
            "scripts/fill.js",
            "references/fields.md",
            "references/layout.json",
            "evals/evals.json",
        }
        for relative in generated - set(files):
            stale = folder / relative
            if stale.exists():
                stale.unlink()
                logger.info("removed %s", stale)
        for relative, content in files.items():
            write_text_atomically(folder / relative, content)
