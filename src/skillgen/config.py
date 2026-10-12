"""Project settings stored in `.skillgen/config.json`."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from skillgen.errors import ConfigError

CONFIG_SCHEMA_VERSION = 1


class Environment(str, Enum):
    """What kind of environment `app_url` points at. The probe refuses production."""

    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class AnalyzerKind(str, Enum):
    """Who performs the analysis step."""

    CLAUDE_CODE = "claude-code"  # headless `claude -p --json-schema`, one route per run
    FILE = "file"  # Claude Code writes analysis.json itself (interactive /skillgen)
    REPLAY = "replay"  # recorded analyses, for tests and fixtures


@dataclass(frozen=True)
class SliceSettings:
    """How much code goes into a page slice (spec section 5, step 1).

    Attributes:
        depth: Import hops followed from the route's entry file.
        max_files: Most files in a slice.
        max_tokens: Most estimated tokens of code in a slice.
    """

    depth: int = 3
    max_files: int = 40
    max_tokens: int = 60_000


@dataclass(frozen=True)
class Settings:
    """Everything in `config.json`.

    Attributes:
        app_name: Display name of the app; also the default skill-name prefix.
        app_url: Base URL of a running copy; empty for code-only generation.
        environment: Kind of environment `app_url` points at.
        should_probe: Run the Playwright probe when `app_url` is set.
        name_prefix: Prefix for skill names; defaults to the slug of `app_name`.
        include: Route globs to keep (empty keeps all).
        exclude: Route globs to drop.
        analyzer: Who performs the analysis step.
        concurrency: Routes analysed at the same time in batch mode.
        slice: Page-slice limits.
        hintpacks: Extra hint-pack folders, relative to the repository.
        skills_dir: Where public skill folders are written, relative to the repository.
    """

    app_name: str = ""
    app_url: str = ""
    environment: Environment = Environment.DEV
    should_probe: bool = False
    name_prefix: str = ""
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    analyzer: AnalyzerKind = AnalyzerKind.CLAUDE_CODE
    concurrency: int = 2
    slice: SliceSettings = field(default_factory=SliceSettings)
    hintpacks: tuple[str, ...] = ()
    skills_dir: str = "skills"


def check_app_url(url: str) -> str:
    """Validate an app URL and return it without a trailing slash.

    Args:
        url: The URL, or an empty string.

    Returns:
        The cleaned URL.

    Raises:
        ConfigError: If the URL is not an absolute http(s) URL.
    """
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ConfigError(f"app URL must look like http://localhost:3000, not {url!r}")
    return url.rstrip("/")


def settings_to_dict(settings: Settings) -> dict[str, Any]:
    """Convert settings to the `config.json` document.

    Args:
        settings: The settings.

    Returns:
        A JSON-ready dictionary.
    """
    data = asdict(settings)
    data["environment"] = settings.environment.value
    data["analyzer"] = settings.analyzer.value
    data["include"] = list(settings.include)
    data["exclude"] = list(settings.exclude)
    data["hintpacks"] = list(settings.hintpacks)
    data["probe"] = data.pop("should_probe")
    return {"schema": CONFIG_SCHEMA_VERSION, **data}


def settings_from_dict(data: dict[str, Any]) -> Settings:
    """Read settings from a `config.json` document, filling in defaults.

    Args:
        data: The parsed document.

    Returns:
        The settings.

    Raises:
        ConfigError: If a value is invalid.
    """
    try:
        slice_data = data.get("slice", {})
        return Settings(
            app_name=str(data.get("app_name", "")),
            app_url=check_app_url(str(data.get("app_url", ""))),
            environment=Environment(data.get("environment", "dev")),
            should_probe=bool(data.get("probe", False)),
            name_prefix=str(data.get("name_prefix", "")),
            include=tuple(str(item) for item in data.get("include", [])),
            exclude=tuple(str(item) for item in data.get("exclude", [])),
            analyzer=AnalyzerKind(data.get("analyzer", "claude-code")),
            concurrency=max(1, int(data.get("concurrency", 2))),
            slice=SliceSettings(**{key: int(value) for key, value in slice_data.items()}),
            hintpacks=tuple(str(item) for item in data.get("hintpacks", [])),
            skills_dir=str(data.get("skills_dir", "skills")),
        )
    except (ValueError, TypeError) as error:
        raise ConfigError(f"config.json has an invalid value: {error}") from error


def update_settings(settings: Settings, **changes: Any) -> Settings:
    """Return settings with some values changed, validating the app URL.

    Args:
        settings: The current settings.
        **changes: Field names and new values.

    Returns:
        The new settings.

    Raises:
        ConfigError: If the app URL is invalid.
    """
    if "app_url" in changes:
        changes["app_url"] = check_app_url(str(changes["app_url"]))
    return replace(settings, **changes)
