"""JSON schemas shipped with skillgen, and validation against them.

Schemas are package data: `page.schema.json` for `page.json`, and one file per CLI
command under `cli/` for `--json` output.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

from skillgen.errors import SchemaError


@cache
def load_schema(name: str) -> dict[str, Any]:
    """Load a schema shipped with skillgen.

    Args:
        name: Path below the schema package without the suffix, such as `page`
            or `cli/routes`.

    Returns:
        The parsed schema.

    Raises:
        SchemaError: If no schema has that name.
    """
    resource = resources.files(__name__).joinpath(f"{name}.schema.json")
    if not resource.is_file():
        raise SchemaError(name, [f"no schema named {name!r}"])
    schema: dict[str, Any] = json.loads(resource.read_text(encoding="utf-8"))
    _validator_class().check_schema(schema)
    return schema


def _validator_class() -> Any:
    """Return the JSON Schema validator, imported on first use.

    `jsonschema` costs about a third of a second to import, which every command paid
    even when it validated nothing. Importing it here keeps that cost on the commands
    that actually read or check a schema.

    Any: the validator class, whose type adds nothing a caller can use here.
    """
    from jsonschema import Draft202012Validator  # noqa: PLC0415 - import cost, see above

    return Draft202012Validator


def list_cli_schemas() -> list[str]:
    """List the CLI commands that have an output schema.

    Returns:
        Command names, sorted.
    """
    folder = resources.files(__name__).joinpath("cli")
    return sorted(
        entry.name.removesuffix(".schema.json")
        for entry in folder.iterdir()
        if entry.name.endswith(".schema.json")
    )


def find_schema_problems(document: object, name: str) -> list[str]:
    """List every way a document breaks a schema.

    Args:
        document: The parsed JSON document.
        name: The schema name, as for `load_schema`.

    Returns:
        One message per violation, with the JSON path; empty when valid.
    """
    validator = _validator_class()(load_schema(name))
    problems = []
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        path = "/".join(str(part) for part in error.absolute_path) or "(root)"
        problems.append(f"{path}: {error.message}")
    return problems


def validate_document(document: object, name: str) -> None:
    """Raise when a document does not match a schema.

    Args:
        document: The parsed JSON document.
        name: The schema name, as for `load_schema`.

    Raises:
        SchemaError: If the document has any violation.
    """
    problems = find_schema_problems(document, name)
    if problems:
        raise SchemaError(name, problems)
