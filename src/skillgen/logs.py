"""Run logs: every command writes a full debug log to `.skillgen/logs/`.

The console shows warnings (more with `-v`); the file always has everything, so a
developer can read or share exactly what happened. Logs stay in the workspace, are
gitignored, and are never exported.
"""

from __future__ import annotations

import logging
import platform
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from skillgen import TOOL_NAME, __version__

LOGS_FOLDER = "logs"
KEPT_LOGS = 30
FILE_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
CONSOLE_FORMAT = "%(levelname)s %(name)s: %(message)s"


def choose_console_level(verbosity: int) -> int:
    """Map `-v` counts to a console log level.

    Args:
        verbosity: 0 for warnings, 1 for info, 2 or more for debug.

    Returns:
        A `logging` level.
    """
    return logging.WARNING - 10 * min(max(verbosity, 0), 2)


def make_log_path(folder: Path, command: str, now: datetime) -> Path:
    """Name a new log file such as `20261008-091500-generate.log`.

    Args:
        folder: The `.skillgen/` folder.
        command: The command name.
        now: The current time.

    Returns:
        The path; the folder is not created.
    """
    return folder / LOGS_FOLDER / f"{now.strftime('%Y%m%d-%H%M%S')}-{command}.log"


def list_logs(folder: Path) -> list[Path]:
    """List run logs, newest first.

    Args:
        folder: The `.skillgen/` folder.

    Returns:
        Log paths.
    """
    return sorted((folder / LOGS_FOLDER).glob("*.log"), reverse=True)


def prune_logs(folder: Path, keep: int = KEPT_LOGS) -> None:
    """Delete all but the newest logs.

    Args:
        folder: The `.skillgen/` folder.
        keep: How many to keep.
    """
    for old in list_logs(folder)[keep:]:
        old.unlink(missing_ok=True)


def stop_logging() -> None:
    """Remove and close every root logging handler owned by the current run."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def start_logging(
    verbosity: int, workspace_folder: Path | None, command: str, argv: Sequence[str]
) -> Path | None:
    """Send logs to the console and, inside a workspace, to a new log file.

    Args:
        verbosity: Number of `-v` flags.
        workspace_folder: The `.skillgen/` folder, or None outside a workspace.
        command: The command being run.
        argv: The arguments, recorded at the top of the log.

    Returns:
        The log file, or None when there is no workspace.
    """
    stop_logging()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(choose_console_level(verbosity))
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    root.addHandler(console)
    if workspace_folder is None:
        return None
    path = make_log_path(workspace_folder, command, datetime.now(timezone.utc))
    path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    root.addHandler(file_handler)
    prune_logs(workspace_folder)
    logging.getLogger(TOOL_NAME).info(
        "%s %s · %s · python %s · %s · cwd %s",
        TOOL_NAME,
        __version__,
        " ".join(argv) or command,
        platform.python_version(),
        platform.platform(),
        Path.cwd(),
    )
    return path
