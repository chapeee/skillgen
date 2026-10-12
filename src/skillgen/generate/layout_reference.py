"""The readable layout reference shipped with a skill: every position `--xy` measured.

The fill call carries only a compact fingerprint of a few landmark fields, enough to
check the live page cheaply. This file holds every measured field, in page and in
anchor-relative coordinates, for an AI that has to check the page by hand. Positions
only ever verify: anything clicked is measured again on the screen at hand.
"""

from __future__ import annotations

import json

from skillgen.generate.inline_setter import choose_landmarks
from skillgen.model.page import PageModel

LAYOUT_REFERENCE_FILE = "references/layout.json"


def render_layout_reference(page: PageModel) -> str | None:
    """Render `references/layout.json` from a page's measured layout.

    Args:
        page: The page model.

    Returns:
        The JSON text, or None when the page has no measured layout.
    """
    if page.layout is None or not page.layout.boxes:
        return None
    boxes = dict(page.layout.boxes)
    landmarks = choose_landmarks(page)
    anchor_key = landmarks[0][0] if landmarks else page.layout.boxes[0][0]
    anchor = boxes[anchor_key]
    landmark_keys = {key for key, _ in landmarks}
    fields = [
        {
            "key": spec.key,
            "label": spec.label,
            "selector": spec.selector,
            "x": boxes[spec.key].left,
            "y": boxes[spec.key].top,
            "width": boxes[spec.key].width,
            "height": boxes[spec.key].height,
            "dx": boxes[spec.key].left - anchor.left,
            "dy": boxes[spec.key].top - anchor.top,
            "landmark": spec.key in landmark_keys,
        }
        | ({"view": view.name} if (view := page.view_of(spec.key)) else {})
        for spec in page.fields
        if spec.key in boxes
    ]
    document = {
        "about": (
            "Where each field sat when this skill was made, measured in a browser. "
            "x and y are page coordinates; dx and dy are relative to the anchor field, so "
            "they hold when the page scrolls or is centred differently. Use them only to "
            "check the live page. A field with a view was measured after reaching that view "
            "(a step, tab or dialog) with its clicks. Measure a field again on screen before "
            "clicking it, and trust nothing here once the page or the window size looks "
            "different."
        ),
        "viewport": {"width": page.layout.viewport_width, "height": page.layout.viewport_height},
        "open": list(page.open_steps),
        "anchor": anchor_key,
        "fields": fields,
    }
    if page.views:
        document["views"] = [
            {"name": view.name, "enter": list(view.enter), "leave": list(view.leave)}
            for view in page.views
        ]
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
