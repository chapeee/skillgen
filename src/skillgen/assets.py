"""Find data folders shipped with skillgen (`hintpacks/`, `claude/`).

In a wheel they live under `skillgen/_data/`; in a source checkout they sit at the
repository root. Both layouts are supported so tests and installs see the same data.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from skillgen import TOOL_NAME
from skillgen.errors import WorkspaceError

_SOURCE_ROOT = Path(__file__).resolve().parent.parent.parent


def find_data_folder(name: str) -> Path:
    """Return the folder holding a shipped data set.

    Args:
        name: `hintpacks` or `claude`.

    Returns:
        The folder path.

    Raises:
        WorkspaceError: If the data is missing from both layouts.
    """
    packaged = Path(str(resources.files(__package__ or TOOL_NAME))) / "_data" / name
    if packaged.is_dir():
        return packaged
    checkout = _SOURCE_ROOT / name
    if checkout.is_dir():
        return checkout
    raise WorkspaceError(f"shipped data folder {name!r} is missing; reinstall {TOOL_NAME}")


def read_fill_engine() -> str:
    """Read the shared fill engine shipped with skillgen.

    The engine is data the generator needs but must not read itself, so this lives at
    the edge with the rest of the file access.

    Returns:
        The engine source; it closes the function the generated header opens.

    Raises:
        WorkspaceError: If the engine is missing from the install.
    """
    engine = resources.files("skillgen.generate").joinpath("fill_engine.js")
    if not engine.is_file():
        raise WorkspaceError(f"the shipped fill engine is missing; reinstall {TOOL_NAME}")
    return engine.read_text("utf-8")


def read_index_template() -> str:
    """Read the index page template shipped with skillgen.

    Returns:
        The template HTML.

    Raises:
        WorkspaceError: If the template is missing from the install.
    """
    template = resources.files("skillgen.generate").joinpath("index_template.html")
    if not template.is_file():
        raise WorkspaceError(f"the shipped index template is missing; reinstall {TOOL_NAME}")
    return template.read_text("utf-8")
