"""The skill index: `skills-index.json` and a self-contained `skills-index.html` (spec section 12).

The graph layout is computed here, so the page needs no library and no network and
works when opened from a zip.
"""

from __future__ import annotations

import html
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from skillgen import TOOL_NAME, __version__
from skillgen.model.page import PageModel, list_dependencies
from skillgen.model.route import RouteEntry
from skillgen.validate.spec import estimate_tokens

LAYOUT_ROUNDS = 220
CALLS_PER_FILL = 8


@dataclass(frozen=True)
class IndexInput:
    """What the index describes.

    Attributes:
        app_name: The app's display name.
        pages: Page models of generated skills.
        routes: Every route, including those without a form.
        skill_sizes: Skill name → `SKILL.md` text length, for the token estimate.
        commit: Source commit.
        generated_on: ISO date of the run.
        detected: Hint packs that matched, shown as the detected stack.
        changed: Skills whose last regeneration changed their model.
    """

    app_name: str
    pages: tuple[PageModel, ...]
    routes: tuple[RouteEntry, ...]
    skill_sizes: dict[str, int]
    commit: str = ""
    generated_on: str = ""
    detected: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()


def build_graph(
    pages: Sequence[PageModel], app_name: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build graph nodes and links: app → skills → sections → fields, plus dependencies.

    Args:
        pages: Page models.
        app_name: The app's name.

    Returns:
        (nodes, links).
    """
    nodes: list[dict[str, Any]] = [{"id": "app", "kind": "app", "label": app_name or "app"}]
    links: list[dict[str, Any]] = []
    for page in pages:
        skill_id = f"skill:{page.skill}"
        nodes.append({"id": skill_id, "kind": "skill", "label": page.skill, "skill": page.skill})
        links.append({"source": "app", "target": skill_id, "kind": "has"})
        sections = {section.id: section.label for section in page.sections}
        for section_id, label in sections.items():
            node_id = f"section:{page.skill}:{section_id}"
            nodes.append({"id": node_id, "kind": "section", "label": label, "skill": page.skill})
            links.append({"source": skill_id, "target": node_id, "kind": "has"})
        for spec in page.fields:
            node_id = f"field:{page.skill}:{spec.key}"
            parent = (
                f"section:{page.skill}:{spec.section}" if spec.section in sections else skill_id
            )
            nodes.append({"id": node_id, "kind": "field", "label": spec.label, "skill": page.skill})
            links.append({"source": parent, "target": node_id, "kind": "has"})
        for link in list_dependencies(page):
            kind = "condition" if link.kind != "options_from" else "dependency"
            links.append(
                {
                    "source": f"field:{page.skill}:{link.source}",
                    "target": f"field:{page.skill}:{link.target}",
                    "kind": kind,
                }
            )
    known = {node["id"] for node in nodes}
    return nodes, [link for link in links if link["source"] in known and link["target"] in known]


def layout_graph(nodes: list[dict[str, Any]], links: list[dict[str, Any]]) -> None:
    """Place nodes with a small deterministic force layout, in place (x, y in 0..1000).

    Args:
        nodes: Nodes; `x` and `y` are added.
        links: Links between node ids.
    """
    count = max(len(nodes), 1)
    for index, node in enumerate(nodes):
        angle = 2 * math.pi * index / count
        radius = 0 if node["kind"] == "app" else 120 + 40 * (index % 7)
        node["x"], node["y"] = 500 + radius * math.cos(angle), 500 + radius * math.sin(angle)
    position = {node["id"]: node for node in nodes}
    pairs = [(position[link["source"]], position[link["target"]]) for link in links]
    for round_number in range(LAYOUT_ROUNDS):
        heat = 1 - round_number / LAYOUT_ROUNDS
        _repel(nodes, heat)
        _attract(pairs, heat)
    _fit(nodes)


def _repel(nodes: list[dict[str, Any]], heat: float) -> None:
    for index, first in enumerate(nodes):
        for second in nodes[index + 1 :]:
            dx, dy = first["x"] - second["x"], first["y"] - second["y"]
            distance_squared = max(dx * dx + dy * dy, 25.0)
            push = 900 * heat / distance_squared
            first["x"] += dx * push
            first["y"] += dy * push
            second["x"] -= dx * push
            second["y"] -= dy * push


def _attract(pairs: list[tuple[dict[str, Any], dict[str, Any]]], heat: float) -> None:
    for first, second in pairs:
        dx, dy = second["x"] - first["x"], second["y"] - first["y"]
        pull = 0.04 * heat
        first["x"] += dx * pull
        first["y"] += dy * pull
        second["x"] -= dx * pull
        second["y"] -= dy * pull


def _fit(nodes: list[dict[str, Any]]) -> None:
    xs, ys = [n["x"] for n in nodes], [n["y"] for n in nodes]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    for node in nodes:
        node["x"] = round(40 + 920 * (node["x"] - min(xs)) / span, 1)
        node["y"] = round(40 + 920 * (node["y"] - min(ys)) / span, 1)


def build_skill_card(page: PageModel, skill_size: int) -> dict[str, Any]:
    """Summarise one skill for its card.

    Args:
        page: The page model.
        skill_size: Length of its `SKILL.md`.

    Returns:
        Card data.
    """
    return {
        "skill": page.skill,
        "route": page.route,
        "title": page.title,
        "purpose": page.purpose,
        "fields": len(page.fields),
        "required": sum(1 for spec in page.fields if spec.is_required),
        "rules": len(page.rules),
        "dependencies": len(list_dependencies(page)),
        "sections": [section.label for section in page.sections],
        "verified": page.is_verified,
        "has_rows": bool(page.groups),
        "needs_record": bool(page.params),
        "skill_tokens": estimate_tokens("x" * skill_size),
        "calls_per_fill": CALLS_PER_FILL,
    }


def build_index_data(data: IndexInput) -> dict[str, Any]:
    """Build the `skills-index.json` document.

    Args:
        data: What to describe.

    Returns:
        The document, including the laid-out graph.
    """
    nodes, links = build_graph(data.pages, data.app_name)
    layout_graph(nodes, links)
    cards = [build_skill_card(page, data.skill_sizes.get(page.skill, 0)) for page in data.pages]
    for card in cards:
        card["changed"] = card["skill"] in data.changed
    return {
        "app": data.app_name,
        "commit": data.commit,
        "generated_on": data.generated_on,
        "generator": f"{TOOL_NAME} {__version__}",
        "detected": list(data.detected),
        "numbers": {
            "routes": len(data.routes),
            "skills": len(data.pages),
            "fields": sum(card["fields"] for card in cards),
            "dependencies": sum(card["dependencies"] for card in cards),
            "verified": sum(1 for card in cards if card["verified"]),
        },
        "skills": cards,
        "no_form": [entry.route for entry in data.routes if entry.has_form is False],
        "graph": {"nodes": nodes, "links": links},
    }


def render_index_html(document: dict[str, Any], template: str) -> str:
    """Render the self-contained index page.

    Args:
        document: The `skills-index.json` document.
        template: The shipped page template, read at the edge and passed in so this
            module keeps no file access of its own.

    Returns:
        The HTML text.
    """
    payload = json.dumps(document, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"{document['app'] or 'App'} skills")
    return template.replace("__TITLE__", title).replace("__DATA__", payload)
