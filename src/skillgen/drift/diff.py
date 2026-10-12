"""Semantic diff between two versions of a page model (spec section 9). Pure."""

from __future__ import annotations

from dataclasses import dataclass

from skillgen.model.page import FieldSpec, PageModel, list_dependencies


@dataclass(frozen=True)
class Change:
    """One meaningful difference between two page models.

    Attributes:
        kind: `field-added`, `field-removed`, `required-changed`, `options-changed`,
            `type-changed`, `label-changed`, `dependency-added`, `dependency-removed`,
            `success-changed` or `submit-changed`.
        subject: The field key or other subject.
        detail: The change in words.
    """

    kind: str
    subject: str
    detail: str


def _describe_required(spec: FieldSpec) -> str:
    if spec.is_required:
        return "required"
    return "required on a condition" if spec.required_if else "optional"


def diff_field(old: FieldSpec, new: FieldSpec) -> list[Change]:
    """Compare two versions of one field.

    Args:
        old: The previous field.
        new: The new field.

    Returns:
        Changes in label, type, requirement and options.
    """
    changes = []
    if old.label != new.label:
        changes.append(Change("label-changed", new.key, f"label {old.label!r} → {new.label!r}"))
    if old.value_type != new.value_type:
        changes.append(
            Change("type-changed", new.key, f"type {old.value_type.value} → {new.value_type.value}")
        )
    if (old.is_required, old.required_if) != (new.is_required, new.required_if):
        changes.append(
            Change(
                "required-changed",
                new.key,
                f"{_describe_required(old)} → {_describe_required(new)}",
            )
        )
    if set(old.options) != set(new.options):
        added = sorted(set(new.options) - set(old.options))
        removed = sorted(set(old.options) - set(new.options))
        parts = [
            f"added {', '.join(added)}" if added else "",
            f"removed {', '.join(removed)}" if removed else "",
        ]
        changes.append(
            Change("options-changed", new.key, "; ".join(part for part in parts if part))
        )
    return changes


def diff_pages(old: PageModel, new: PageModel) -> list[Change]:
    """List what changed between two versions of a page model.

    Args:
        old: The previous model.
        new: The new model.

    Returns:
        Changes in field order of the new model, then removals, then page-level changes.
    """
    old_fields = {spec.key: spec for spec in old.fields}
    new_fields = {spec.key: spec for spec in new.fields}
    changes: list[Change] = []
    for spec in new.fields:
        previous = old_fields.get(spec.key)
        if previous is None:
            changes.append(Change("field-added", spec.key, f"new field {spec.label!r}"))
        else:
            changes += diff_field(previous, spec)
    changes += [
        Change("field-removed", key, f"field {spec.label!r} is gone")
        for key, spec in old_fields.items()
        if key not in new_fields
    ]
    old_links = {(d.source, d.target, d.kind) for d in list_dependencies(old)}
    new_links = {(d.source, d.target, d.kind) for d in list_dependencies(new)}
    changes += [
        Change("dependency-added", t, f"{s} → {t} ({k})")
        for s, t, k in sorted(new_links - old_links)
    ]
    changes += [
        Change("dependency-removed", t, f"{s} → {t} ({k})")
        for s, t, k in sorted(old_links - new_links)
    ]
    return changes + _diff_submit(old, new)


def _diff_submit(old: PageModel, new: PageModel) -> list[Change]:
    if (old.submit is None) != (new.submit is None):
        return [Change("submit-changed", "submit", "submit control appeared or disappeared")]
    if old.submit is None or new.submit is None:
        return []
    changes = []
    if old.submit.selector != new.submit.selector or old.submit.label != new.submit.label:
        changes.append(
            Change("submit-changed", "submit", f"{old.submit.label!r} → {new.submit.label!r}")
        )
    if old.submit.success != new.submit.success:
        changes.append(Change("success-changed", "submit", "the success signal changed"))
    return changes
