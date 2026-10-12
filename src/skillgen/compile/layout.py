"""Attach the probe's measurements to the merged fields as a page layout. Pure."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from skillgen.model.page import Box, FieldSpec, Layout, PageModel
from skillgen.model.probe import ProbedField, ProbedPage


def find_measured_control(spec: FieldSpec, probe: ProbedPage) -> ProbedField | None:
    """Find the probed control measured with exactly the selector the skill will use.

    Matching on the selector alone is deliberate. A skill checks a box by reading its
    selector back; if the analysis chose a different selector than the probe saw, the
    box would describe another element, so such a field gets no box at all.

    Args:
        spec: The merged field.
        probe: The probe result.

    Returns:
        The probed control with a box, or None.
    """
    return next(
        (
            probed
            for probed in probe.fields
            if probed.box and not probed.is_repeated and probed.selector == spec.selector
        ),
        None,
    )


def carry_layout(previous: PageModel | None, page: PageModel) -> Layout | None:
    """Keep an earlier run's x/y for the fields whose selector has not changed.

    Safe because x/y only verifies: the skill checks the live page against it before
    trusting it, and anything it clicks is measured again on the screen at hand.

    Args:
        previous: The page model before this run, if any.
        page: The page model this run built.

    Returns:
        The earlier layout cut to the fields that still match, or None.
    """
    if previous is None or previous.layout is None:
        return None
    old = {spec.key: spec.selector for spec in previous.fields}
    new = {spec.key: spec.selector for spec in page.fields if not spec.group}
    boxes = tuple(
        (key, box) for key, box in previous.layout.boxes if key in new and old.get(key) == new[key]
    )
    return replace(previous.layout, boxes=boxes) if boxes else None


def build_layout(fields: Sequence[FieldSpec], probe: ProbedPage | None) -> Layout | None:
    """Build the page layout from the probe's measurements of the merged fields.

    Fields in repeating rows are left out: their selector names one row of many, so a
    box would describe whichever row happened to come first.

    Args:
        fields: The merged fields, in fill order.
        probe: The probe result, or None when the probe did not run.

    Returns:
        The layout, or None when there is nothing measured to build one from.
    """
    if probe is None or probe.viewport_width <= 0:
        return None
    boxes: list[tuple[str, Box]] = []
    for spec in fields:
        if spec.group:
            continue
        probed = find_measured_control(spec, probe)
        if probed is not None and probed.box is not None:
            boxes.append((spec.key, probed.box))
    if not boxes:
        return None
    return Layout(
        viewport_width=probe.viewport_width,
        viewport_height=probe.viewport_height,
        boxes=tuple(boxes),
    )
