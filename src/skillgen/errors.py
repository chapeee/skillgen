"""Every exception skillgen raises on purpose.

Callers catch `SkillgenError` to handle any expected failure; anything else is a bug.
"""

from __future__ import annotations

from enum import Enum


class SkillgenError(Exception):
    """Base class for every expected skillgen failure."""


class WorkspaceError(SkillgenError):
    """The `.skillgen/` workspace is missing, unreadable or malformed."""


class ConfigError(SkillgenError):
    """`config.json` or a command-line option has an invalid value."""


class SchemaError(SkillgenError):
    """A JSON document does not match its schema.

    Attributes:
        schema_name: Name of the schema that rejected the document.
        problems: Human-readable descriptions of each violation.
    """

    def __init__(self, schema_name: str, problems: list[str]) -> None:
        self.schema_name = schema_name
        self.problems = problems
        summary = "; ".join(problems[:3])
        super().__init__(f"document does not match schema {schema_name!r}: {summary}")


class ModelError(SkillgenError):
    """A page model is internally inconsistent (unknown keys, cycles, bad values)."""


class RouteError(SkillgenError):
    """A route cannot be found, parsed or named."""


class GraphError(SkillgenError):
    """The code graph cannot be built or read."""


class AnalysisError(SkillgenError):
    """The analysis step failed or returned output that does not fit the schema."""


class HintPackError(SkillgenError):
    """A hint pack file is malformed."""


class ValidationFailedError(SkillgenError):
    """A generated skill failed one or more checks.

    Attributes:
        problems: Human-readable descriptions of each failed check.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(f"{len(problems)} check(s) failed: " + "; ".join(problems[:3]))


class ProbeError(SkillgenError):
    """The runtime probe cannot run or failed on a page."""


class ProbeUnavailableError(ProbeError):
    """The `probe` extra (Playwright) is not installed."""


class UnsafeEnvironmentError(ProbeError):
    """The probe was pointed at an environment not marked as dev or staging."""


class Need(str, Enum):
    """Something a run cannot do on its own, so whoever runs it takes the next step."""

    ANALYSIS = "analysis"  # the agent running skillgen reads the code itself
    LIMIT = "limit"  # the AI's own usage limit is reached: wait for it, then run again
    URL = "url"  # the developer gives the dev copy's address
    PROBE = "probe"  # the probe extra (Playwright) is not installed
    CHROMIUM = "chromium"  # Playwright is there, its Chromium is not downloaded
    SERVER = "server"  # nothing answers at the dev copy's address
    LOGIN = "login"  # the page asks the developer to sign in
    OPEN = "open"  # no field showed: something must be clicked to show the form


class ActionNeededError(ProbeError):
    """The probe stopped at something only the developer can do.

    Attributes:
        need: What is needed.
        detail: The URL or reason the need is about.
    """

    def __init__(self, need: Need, detail: str, message: str) -> None:
        self.need = need
        self.detail = detail
        super().__init__(message)


class RuleError(SkillgenError):
    """A user rule cannot be parsed, or it would loosen a rule the app enforces."""


class ExportError(SkillgenError):
    """Export failed, for example because the secret scan found something."""
