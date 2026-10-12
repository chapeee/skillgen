"""Builders for small synthetic page models used across tests."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

from skillgen.model.facts import Provenance, Source
from skillgen.model.page import FieldSpec, PageModel, Strategy, SubmitSpec, ValueType
from skillgen.model.serialize import page_from_dict

BENCH = Path(__file__).resolve().parent / "bench"
PROBED = Provenance(sources=(Source.RUNTIME_PROBED, Source.EXTRACTED), confidence=0.985)


def load_bench_page() -> PageModel:
    return page_from_dict(json.loads((BENCH / "page.json").read_text(encoding="utf-8")))


def load_wizard_analysis() -> dict[str, Any]:
    analysis: dict[str, Any] = json.loads((BENCH / "wizard-analysis.json").read_text("utf-8"))
    return analysis


def load_wizard_page() -> PageModel:
    """The bench wizard: tabs, three steps, a dialog and a field shown for one choice."""
    from skillgen.compile.merge import MergeInput, build_page_model  # noqa: PLC0415

    merged = build_page_model(
        MergeInput(route="/wizard", skill="bench-wizard", analysis=load_wizard_analysis())
    )
    return merged.page


def make_field(key: str, **changes: Any) -> FieldSpec:
    base = FieldSpec(
        key=key,
        label=key.replace("_", " ").capitalize(),
        value_type=ValueType.TEXT,
        strategy=Strategy.NATIVE_INPUT,
        selector=f"#{key}",
        provenance=PROBED,
    )
    return replace(base, **changes)


def make_page(fields: list[FieldSpec], **changes: Any) -> PageModel:
    base = PageModel(
        route="/things/new",
        skill="demo-things-new",
        title="New thing",
        app_name="Demo",
        app_url="https://demo.example.com",
        fields=tuple(fields),
        submit=SubmitSpec(selector="button[type=submit]", label="Save"),
    )
    return replace(base, **changes)


def load_script(path: Path) -> ModuleType:
    """Import a standalone script (such as the bench's serve.py) as a module."""
    spec = importlib.util.spec_from_file_location(f"bench_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
