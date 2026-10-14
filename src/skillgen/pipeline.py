"""Run the per-route pipeline: slice, (probe), analyse, merge, generate, validate.

This module touches files and subprocesses; the steps it calls are pure.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from skillgen.analyze.prompt import (
    PROMPT_VERSION,
    AnalysisRequest,
    build_analysis_prompt,
    build_route_listing_prompt,
)
from skillgen.analyze.runner import (
    Analyzer,
    add_schema_to_prompt,
    check_analysis,
    list_routes_with_claude,
    read_analysis_file,
    schema_for_claude,
)
from skillgen.assets import find_data_folder, read_fill_engine, read_index_template
from skillgen.compile.layout import build_layout, carry_layout
from skillgen.compile.merge import (
    MergeInput,
    MergeResult,
    build_page_model,
    find_open_candidates,
    find_view_candidates,
)
from skillgen.compile.unopened import describe_missed, find_missed_on_page
from skillgen.config import Settings
from skillgen.drift.diff import diff_pages
from skillgen.errors import (
    ActionNeededError,
    AnalysisError,
    GraphError,
    Need,
    ProbeError,
    RouteError,
)
from skillgen.generate.folder import SKILL_FILE, build_skill_files
from skillgen.generate.index_page import IndexInput, build_index_data, render_index_html
from skillgen.generate.user_rules import extract_user_block
from skillgen.graph.codegraph import (
    CodeGraph,
    build_code_graph,
    find_graph_staleness,
    load_code_graph,
    save_code_graph,
)
from skillgen.graph.connections import (
    GRAPH_FILE,
    GRAPHIFY_OUT,
    GRAPHIFY_TOOL_VERSION,
    GraphifyGraph,
    build_graph,
    explain_node,
    load_graph_metadata,
)
from skillgen.graph.hubs import rank_router_candidates
from skillgen.graph.slice import PageSlice, resolve_component, slice_page
from skillgen.model.page import Layout, PageModel, View
from skillgen.model.probe import ProbedPage
from skillgen.model.route import Question, RouteCandidate, RouteEntry, RouteTable
from skillgen.model.serialize import page_to_dict
from skillgen.routes.astgrep import find_declared_routes
from skillgen.routes.folders import find_folder_routes
from skillgen.routes.hintpacks import load_hint_packs
from skillgen.routes.merge import find_pattern_files, merge_routes, rename_route
from skillgen.routes.naming import slugify
from skillgen.routes.paths import check_route_text, normalize_route
from skillgen.validate.model_checks import check_page_model
from skillgen.validate.scan import scan_files
from skillgen.validate.spec import check_skill_files, find_size_notes
from skillgen.workspace import WORKSPACE_DIR, Workspace, write_json, write_text_atomically

logger = logging.getLogger(__name__)

GRAPH_CACHE = "graph.json"
ANALYSIS_FILE = "analysis.json"
# What the saved analysis was made from, and what the last request asked about.
ANALYSIS_FINGERPRINT = "analysis.fingerprint"
REQUEST_FINGERPRINT = "request.fingerprint"
# Marks how a fingerprint was made; a record without it predates this scheme.
FINGERPRINT_SCHEME = "analysis-v2:"


def choose_prefix(settings: Settings, root: Path, name: str = "") -> str:
    """Pick the skill-name prefix: `--name`, then config, then the folder name.

    Args:
        settings: Project settings.
        root: The repository root.
        name: The prefix the developer passed, if any.

    Returns:
        A slug to put before every route slug.
    """
    return slugify(name or settings.name_prefix or settings.app_name or root.name)


def read_source_commit(root: Path) -> str:
    """Return the short commit hash of the repository, or an empty string.

    Args:
        root: The repository root.

    Returns:
        The hash, such as `9f3c2e1`.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def generated_paths(workspace: Workspace) -> tuple[str, ...]:
    """List folders and files skillgen writes, which are never app code.

    Args:
        workspace: The workspace.

    Returns:
        Repository-relative paths.
    """
    skills_dir = workspace.read_settings().skills_dir if workspace.exists() else "skills"
    return (WORKSPACE_DIR, skills_dir, "dist", "skills-index.html", "skills-index.json")


def load_graph(workspace: Workspace, *, should_refresh: bool = False) -> CodeGraph:
    """Return the code graph, building it with Graphify when needed.

    Args:
        workspace: The workspace.
        should_refresh: Rebuild even when a cached graph exists.

    Returns:
        The code graph.

    Raises:
        GraphError: If Graphify fails.
    """
    cache = workspace.cache_folder / GRAPH_CACHE
    cached = None if should_refresh else load_code_graph(cache)
    if cached is not None:
        stale = (
            "legacy graph cache has no source snapshot"
            if cached[0].source_snapshot is None
            else find_graph_staleness(
                cached[0], workspace.root, cached[1], generated_paths(workspace)
            )
        )
        if not stale:
            return cached[0]
        logger.info("rebuilding the code graph: %s", stale)
    graph = build_code_graph(
        workspace.root, workspace.cache_folder / "graphify", generated_paths(workspace)
    )
    save_code_graph(graph, cache)
    return graph


def load_graphify_graph(workspace: Workspace, graph: CodeGraph) -> GraphifyGraph | None:
    """Return the graph Graphify's own queries read, building it when it is out of date.

    It is a second, richer build of the same repository, so it is made only when a
    prompt is about to be written and reused until the code changes. Staleness is the
    same question the collapsed graph asks, with Graphify's graph file as the stamp.

    Args:
        workspace: The workspace.
        graph: The collapsed graph, which names the files to check.

    Returns:
        The graph, or None when Graphify could not build one.
    """
    path = workspace.cache_folder / GRAPHIFY_OUT / GRAPH_FILE
    if path.is_file():
        metadata = load_graph_metadata(path)
        stale = "missing rich graph metadata"
        if graph.source_snapshot is not None and metadata is not None:
            fingerprint, tool_version = metadata
            stale = find_graph_staleness(
                graph, workspace.root, path.stat().st_mtime, generated_paths(workspace)
            )
            if not stale and fingerprint != graph.source_snapshot.fingerprint:
                stale = "rich graph source snapshot changed"
            if not stale and tool_version != GRAPHIFY_TOOL_VERSION:
                stale = "rich graph tool version changed"
        if not stale:
            assert metadata is not None
            return GraphifyGraph(
                path=path,
                fingerprint=metadata[0],
                tool_version=metadata[1],
                answer_cache=workspace.cache_folder / "explain",
            )
        logger.info("rebuilding graphify's graph: %s", stale)
    try:
        return build_graph(
            workspace.root,
            workspace.cache_folder,
            fingerprint=graph.source_snapshot.fingerprint if graph.source_snapshot else "",
            answer_cache=workspace.cache_folder / "explain",
        )
    except OSError as error:
        logger.warning("graphify's query graph could not be built: %s", error)
        return None


def describe_page_connections(
    workspace: Workspace,
    graph: CodeGraph | None,
    entry_files: Sequence[str],
    graphify_graph: GraphifyGraph | None = None,
    *,
    should_load_graphify: bool = True,
) -> tuple[str, ...]:
    """Ask Graphify to explain the page's own component, for the analysis to read.

    One question per route: the component the route resolves to. What it contains and
    calls is what an analysis cannot see in a flat list of paths.

    Args:
        workspace: The workspace.
        graph: The collapsed graph, or None when there is none.
        entry_files: The route's entry files.
        graphify_graph: The already-built Graphify graph shared by the run.
        should_load_graphify: Build one lazily for a standalone route request.

    Returns:
        Graphify's answer as lines; empty when it has none.
    """
    if graph is None or not entry_files:
        return ()
    built = graphify_graph
    if built is None and should_load_graphify:
        built = load_graphify_graph(workspace, graph)
    if built is None:
        return ()
    return tuple(explain_node(built, PurePosixPath(entry_files[0]).name))


def hint_pack_folders(workspace: Workspace, settings: Settings) -> list[Path]:
    """List hint pack folders: the shipped ones, then the project's own.

    Args:
        workspace: The workspace.
        settings: Project settings.

    Returns:
        Folders in override order.
    """
    return [
        find_data_folder("hintpacks"),
        *(workspace.root / extra for extra in settings.hintpacks),
    ]


def find_route_candidates(
    workspace: Workspace, settings: Settings, graph: CodeGraph | None
) -> list[RouteCandidate]:
    """Run every automatic route source.

    Args:
        workspace: The workspace.
        settings: Project settings.
        graph: The code graph, used to resolve route components; optional.

    Returns:
        Candidates from folder conventions and declared routes.
    """
    packs = load_hint_packs(hint_pack_folders(workspace, settings))
    candidates = find_folder_routes(workspace.root, packs.folders)

    def resolve(name: str, declared_in: str) -> str | None:
        return resolve_component(graph, name, declared_in) if graph else None

    candidates += find_declared_routes(
        workspace.root, packs.routers, resolve, generated_paths(workspace)
    )
    if graph is not None:
        candidates += [
            RouteCandidate(route, "graph:graphify", (file,)) for route, file in graph.routes
        ]
    return candidates


def discover_routes(
    workspace: Workspace,
    settings: Settings,
    *,
    extra_routes: Sequence[str] = (),
    prefix: str = "",
    graph: CodeGraph | None = None,
    extra_candidates: Sequence[RouteCandidate] = (),
    route_candidates: Sequence[RouteCandidate] | None = None,
) -> RouteTable:
    """Find routes from every source, merge them into `routes.json`, and save it.

    Args:
        workspace: The workspace.
        settings: Project settings (include and exclude globs).
        extra_routes: Routes the developer named with `--route`.
        prefix: Skill-name prefix chosen with `--name`.
        graph: The code graph, if already built.
        extra_candidates: Candidates from other sources, such as Claude Code.
        route_candidates: Automatic candidates already found for this run.

    Returns:
        The merged table.
    """
    candidates = (
        list(route_candidates)
        if route_candidates is not None
        else find_route_candidates(workspace, settings, graph)
    )
    for route in extra_routes:
        check_route_text(route)
    candidates += [RouteCandidate(route, "user") for route in extra_routes]
    candidates += list(extra_candidates)
    table = merge_routes(
        workspace.read_routes(),
        candidates,
        choose_prefix(settings, workspace.root, prefix),
        settings.include,
        settings.exclude,
    )
    workspace.write_routes(table)
    return table


def apply_open_steps(
    workspace: Workspace, table: RouteTable, route: str, steps: Sequence[str]
) -> RouteTable:
    """Record what to click before one route's form is on screen, and save `routes.json`.

    Args:
        workspace: The workspace.
        table: The current table.
        route: The route.
        steps: CSS selectors or `text:Label` steps, in click order.

    Returns:
        The updated table.
    """
    chosen = tuple(step.strip() for step in steps if step.strip())
    updated = RouteTable(
        entries=tuple(
            replace(entry, open_steps=chosen) if entry.route == route else entry
            for entry in table.entries
        )
    )
    workspace.write_routes(updated)
    return updated


def apply_skill_name(workspace: Workspace, table: RouteTable, route: str, name: str) -> RouteTable:
    """Give one route the developer's skill name and save `routes.json`.

    Args:
        workspace: The workspace.
        table: The current table.
        route: The route.
        name: The chosen name.

    Returns:
        The updated table.

    Raises:
        RouteError: If the name is invalid or taken.
    """
    updated = rename_route(table, route, name)
    workspace.write_routes(updated)
    return updated


def apply_prefix(workspace: Workspace, settings: Settings, prefix: str) -> RouteTable:
    """Rename every route whose name is not locked with a new prefix, and save.

    Args:
        workspace: The workspace.
        settings: Project settings.
        prefix: The developer's prefix.

    Returns:
        The updated table.
    """
    table = merge_routes(
        workspace.read_routes(), [], choose_prefix(settings, workspace.root, prefix)
    )
    workspace.write_routes(table)
    return table


def ensure_route(
    workspace: Workspace,
    settings: Settings,
    route: str,
    graph: CodeGraph | None = None,
    *,
    route_candidates: Sequence[RouteCandidate] | None = None,
) -> RouteEntry:
    """Return a route's entry, adding the route to `routes.json` when it is new.

    Args:
        workspace: The workspace.
        settings: Project settings.
        route: A route or skill name.
        graph: The code graph, which resolves a route's component to its own file.
            Without it a router that declares every route is the only entry on offer,
            so saved files are then left alone rather than replaced with it.
        route_candidates: Automatic candidates already found for this run.

    Returns:
        The entry.

    Raises:
        RouteError: If the route cannot be added.
    """
    check_route_text(route)
    table = workspace.read_routes()
    found = table.find(route)
    if found is not None and found.entry_files and graph is None:
        return found
    if found is None and not route.startswith("/"):
        raise RouteError(f"no route or skill named {route!r}; routes start with /")
    # Without its code files a route's slice is empty and the analysis starts blind, so
    # they are looked up in the routes found in the code: the same route, or the pattern
    # a concrete page belongs to.
    candidates = (
        list(route_candidates)
        if route_candidates is not None
        else find_route_candidates(workspace, settings, graph)
    )
    if found is not None:
        return _fill_entry_files(workspace, table, found, candidates, may_replace=graph is not None)
    wanted = normalize_route(route)
    discovered = [c for c in candidates if normalize_route(c.route) == wanted]
    files = () if discovered else find_pattern_files(route, candidates)
    table = merge_routes(
        table,
        [*discovered, RouteCandidate(route, "user", files)],
        choose_prefix(settings, workspace.root),
    )
    workspace.write_routes(table)
    entry = table.find(route) or table.find(route.rstrip("/"))
    if entry is None:
        raise RouteError(f"route {route!r} could not be added")
    return entry


def _fill_entry_files(
    workspace: Workspace,
    table: RouteTable,
    entry: RouteEntry,
    candidates: list[RouteCandidate],
    *,
    may_replace: bool = False,
) -> RouteEntry:
    """Give a saved route the code files found for it now, and save them.

    Args:
        workspace: The workspace.
        table: The saved route table.
        entry: The route's saved entry.
        candidates: Routes found in the code now.
        may_replace: Replace files the route already has. The code is the source of
            truth, as `routes` treats it, so a route whose entry was saved before its
            component could be resolved is corrected instead of staying wrong forever.

    Returns:
        The entry, with its files updated when any were found.
    """
    if entry.entry_files and not may_replace:
        return entry
    wanted = normalize_route(entry.route)
    exact = [c for c in candidates if normalize_route(c.route) == wanted]
    files = tuple(dict.fromkeys(file for c in exact for file in c.entry_files))
    files = files or find_pattern_files(entry.route, candidates)
    if not files or files == entry.entry_files:
        return entry
    updated = RouteTable(
        entries=tuple(
            replace(item, entry_files=files) if item.route == entry.route else item
            for item in table.entries
        )
    )
    workspace.write_routes(updated)
    logger.info("%s: code files found: %s", entry.route, ", ".join(files))
    return updated.find(entry.route) or entry


def refresh_entry_files(
    workspace: Workspace,
    settings: Settings,
    entries: Sequence[RouteEntry],
    graph: CodeGraph | None,
    *,
    route_candidates: Sequence[RouteCandidate] | None = None,
) -> list[RouteEntry]:
    """Replace chosen routes' saved code files with the ones the code shows now.

    `ensure_route` does this for one named route; a run over every route reads the
    saved table instead, so without this a route whose entry was saved before its
    component could be resolved keeps slicing the whole app.

    Only with a graph: without one a component cannot be resolved and the router that
    declares every route is the only answer on offer, which is worse than what is
    already saved. Routes are neither added nor dropped here; that is what `routes` does.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entries: The routes the run will work on.
        graph: The code graph, or None.
        route_candidates: Automatic candidates already found for this run.

    Returns:
        The entries, with their code files updated.
    """
    if graph is None or not entries:
        return list(entries)
    found: dict[str, tuple[str, ...]] = {}
    candidates = (
        list(route_candidates)
        if route_candidates is not None
        else find_route_candidates(workspace, settings, graph)
    )
    for candidate in candidates:
        key = normalize_route(candidate.route)
        found[key] = tuple(dict.fromkeys((*found.get(key, ()), *candidate.entry_files)))
    changed = {
        entry.route: found[normalize_route(entry.route)]
        for entry in entries
        if found.get(normalize_route(entry.route), ()) not in ((), entry.entry_files)
    }
    if not changed:
        return list(entries)
    table = workspace.read_routes()
    updated = RouteTable(
        entries=tuple(
            replace(item, entry_files=changed[item.route]) if item.route in changed else item
            for item in table.entries
        )
    )
    workspace.write_routes(updated)
    for route, files in changed.items():
        logger.info("%s: code files now %s", route, ", ".join(files))
    return [updated.find(entry.route) or entry for entry in entries]


def restore_skill_names(workspace: Workspace, routes_text: str) -> None:
    """Put back the skill names a run did not earn, keeping what it learnt about the code.

    A run that writes no skill must not leave a rename behind. The code files it found
    are facts about the code, not choices, so they stay: reverting the whole file would
    throw away a corrected entry and leave the next run slicing the wrong files.

    Args:
        workspace: The workspace.
        routes_text: The `routes.json` text as the run found it.
    """
    saved = {
        str(item.get("route", "")): str(item.get("skill", ""))
        for item in json.loads(routes_text).get("routes", [])
    }
    table = workspace.read_routes()
    reverted = tuple(
        replace(entry, skill=saved[entry.route])
        if saved.get(entry.route) and saved[entry.route] != entry.skill
        else entry
        for entry in table.entries
    )
    if reverted != table.entries:
        workspace.write_routes(RouteTable(entries=reverted))


def build_slice(
    workspace: Workspace, settings: Settings, entry: RouteEntry, graph: CodeGraph | None
) -> PageSlice:
    """Build a route's page slice, or a slice of its entry files when there is no graph.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entry: The route.
        graph: The code graph, if available.

    Returns:
        The slice.
    """
    files = [path for path in entry.entry_files if (workspace.root / path).is_file()]
    sizes = {
        path: (workspace.root / path).stat().st_size
        for path in (graph.files if graph else files)
        if (workspace.root / path).is_file()
    }
    if graph is None:
        return PageSlice(files=tuple((path, 0) for path in files))
    # The first entry file is the page itself; later ones (such as the router file
    # that declares the route) are context and would pull in every sibling page.
    return slice_page(
        graph,
        files[:1],
        sizes,
        context_files=files[1:],
        depth=settings.slice.depth,
        max_files=settings.slice.max_files,
        max_tokens=settings.slice.max_tokens,
    )


def prepare_route(
    workspace: Workspace,
    settings: Settings,
    entry: RouteEntry,
    graph: CodeGraph | None,
    probe: ProbedPage | None = None,
    *,
    graphify_graph: GraphifyGraph | None = None,
    should_load_graphify: bool = True,
) -> AnalysisRequest:
    """Build the analysis request and save the slice and prompt for the route.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entry: The route.
        graph: The code graph, if available.
        probe: The probe result, if the probe ran.
        graphify_graph: The already-built Graphify graph, if available.
        should_load_graphify: Build one lazily for a standalone route request.

    Returns:
        The analysis request.
    """
    page_slice = build_slice(workspace, settings, entry, graph)
    request = AnalysisRequest(
        route=entry.route,
        skill=entry.skill,
        app_name=settings.app_name,
        slice_files=page_slice.paths,
        is_slice_truncated=page_slice.is_truncated,
        probe_summary=summarize_probe(probe) if probe else {},
        connection_lines=describe_page_connections(
            workspace,
            graph,
            entry.entry_files,
            graphify_graph,
            should_load_graphify=should_load_graphify,
        ),
    )
    folder = workspace.page_folder(entry.skill)
    write_json(
        folder / "slice.json",
        {
            "route": entry.route,
            "files": [list(item) for item in page_slice.files],
            "truncated": page_slice.is_truncated,
            "estimated_tokens": page_slice.estimated_tokens,
        },
    )
    # The schema goes in the file, not only to `claude -p` as `--json-schema`: whoever
    # answers this prompt by hand has no other way to know the contract, and guessing
    # it costs a round trip per mistake.
    prompt = add_schema_to_prompt(build_analysis_prompt(request), "page-analysis")
    write_text_atomically(folder / "prompt.md", prompt + "\n")
    return request


def summarize_probe(probe: ProbedPage) -> dict[str, object]:
    """Reduce a probe result to what the analysis prompt needs.

    Args:
        probe: The probe result.

    Returns:
        A small JSON-ready summary without evidence.
    """
    return {
        "title": probe.title,
        "fields": [
            {
                "key": f.key,
                "label": f.label,
                "selector": f.selector,
                "strategy": f.strategy.value,
                "required": f.is_required,
                "options": list(f.options[:20]),
                "visible": f.is_visible,
            }
            for f in probe.fields
        ],
        "clickable": [
            {
                "label": item.get("label", ""),
                "role": item.get("role", ""),
                "click": item.get("step", ""),
                "opens_something": bool(item.get("collapsed") or item.get("opens")),
            }
            for item in probe.clickables
            if item.get("visible")
            and not any(item.get(flag) for flag in ("chrome", "leaves", "risky", "disabled"))
        ],
        "submit": {"selector": probe.submit_selector, "label": probe.submit_label},
    }


@dataclass(frozen=True)
class RouteOutcome:
    """What happened to one route.

    Attributes:
        route: The route.
        skill: The skill name.
        status: `written`, `no-form`, `invalid`, `failed`, `exists` or `needs`.
        problems: Check failures or the error message.
        open_questions: Unanswered questions for this skill.
        skill_folder: Where the skill was written, if it was.
        is_verified: True when the probe proved every required field.
        measured_fields: Fields that got x/y; 0 without `--xy` or when none showed.
        need: What the run could not do on its own, for whoever runs it to do next.
        need_detail: The URL or reason the need is about.
    """

    route: str
    skill: str
    status: str
    problems: tuple[str, ...] = ()
    open_questions: int = 0
    skill_folder: str = ""
    is_verified: bool = False
    measured_fields: int = 0
    need: Need | None = None
    need_detail: str = ""


def merge_questions(old: Iterable[Question], skill: str, new: Iterable[Question]) -> list[Question]:
    """Replace one skill's questions, keeping answers given to the same subjects.

    Args:
        old: Every question in `questions.json`.
        skill: The skill being regenerated.
        new: The questions the merge raised now.

    Returns:
        The full list to save.
    """
    old_list = list(old)
    answered = {q.subject: q.answer for q in old_list if q.skill == skill and q.answer}
    others = [q for q in old_list if q.skill != skill]
    fresh = [replace(q, answer=answered.get(q.subject, q.answer)) for q in new]
    kept_answers = [
        q
        for q in old_list
        if q.skill == skill and q.answer and q.subject not in {f.subject for f in fresh}
    ]
    return [*others, *kept_answers, *fresh]


def next_version(old: PageModel | None, new: PageModel) -> int:
    """Bump the page version when the model changed.

    Args:
        old: The previous model, if any.
        new: The new model (its version is ignored).

    Returns:
        The version to store.
    """
    if old is None:
        return 1
    strip = {"version", "source_commit"}
    before = {k: v for k, v in page_to_dict(old).items() if k not in strip}
    after = {k: v for k, v in page_to_dict(new).items() if k not in strip}
    return old.version if before == after else old.version + 1


@dataclass(frozen=True)
class GenerateOptions:
    """Choices for one generate run.

    Attributes:
        analyzer: Who performs code analysis; absent for URL-only generation.
        probe: In code mode, a saved capture used only to add x/y. In URL mode,
            the read-only capture supplying the page's facts and x/y.
        measure_layout: Measures the code-built page on the dev copy (`--xy`); when set,
            its layout is used instead of the capture's.
        description: A developer-chosen description.
        should_save_analysis: Save the analysis next to page.json.
        should_reuse_analysis: Reuse a saved analysis made from the same prompt and the
            same code, instead of analysing again.
        graphify_graph: The richer Graphify graph shared by every route in this run.
        should_load_graphify: Build the richer graph lazily for standalone route calls.
        is_url_mode: Use observed controls as facts instead of code analysis.
    """

    analyzer: Analyzer | None = None
    probe: ProbedPage | None = None
    description: str = ""
    should_save_analysis: bool = True
    should_reuse_analysis: bool = False
    graph: CodeGraph | None = field(default=None)
    measure_layout: Callable[[PageModel], Layout | None] | None = None
    graphify_graph: GraphifyGraph | None = None
    should_load_graphify: bool = True
    is_url_mode: bool = False


def analyze_route(
    workspace: Workspace, settings: Settings, entry: RouteEntry, options: GenerateOptions
) -> dict[str, Any]:
    """Prepare and analyse one route; safe to run for several routes at once.

    Only the route's own page folder is written.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entry: The route.
        options: Analyzer, graph and probe.

    Returns:
        The validated page analysis.

    Raises:
        AnalysisError: If the analysis fails.
    """
    if options.analyzer is None:
        raise AnalysisError("code generation requires an analyzer")
    # The code says what a page means; the page says what is really on it. A capture is
    # used only when it was taken on this route, which is what `probe_for_route` checks.
    request = prepare_route(
        workspace,
        settings,
        entry,
        options.graph,
        probe_for_route(workspace, settings, entry),
        graphify_graph=options.graphify_graph,
        should_load_graphify=options.should_load_graphify,
    )
    logger.info(
        "%s: slice has %d file(s): %s",
        entry.route,
        len(request.slice_files),
        ", ".join(request.slice_files),
    )
    folder = workspace.page_folder(entry.skill)
    fingerprint = fingerprint_request(workspace, request)
    if options.should_reuse_analysis:
        reused = find_reusable_analysis(folder, fingerprint, find_newest_source(workspace, request))
        if reused is not None:
            logger.info("%s: analysis cache hit; analysis inputs unchanged", entry.route)
            return reused
        logger.info("%s: analysis cache miss; running the analyzer", entry.route)
        write_text_atomically(folder / REQUEST_FINGERPRINT, fingerprint)
    started = time.monotonic()
    analysis = options.analyzer.analyze(request)
    logger.info(
        "%s: analysis done in %.1fs with %s (%d field(s), has_form=%s)",
        entry.route,
        time.monotonic() - started,
        type(options.analyzer).__name__,
        len(analysis.get("fields", [])),
        analysis.get("has_form"),
    )
    if options.should_save_analysis:
        write_json(folder / ANALYSIS_FILE, analysis)
    if options.should_reuse_analysis:
        write_text_atomically(folder / ANALYSIS_FINGERPRINT, fingerprint)
    return analysis


def fingerprint_request(workspace: Workspace, request: AnalysisRequest) -> str:
    """Fingerprint every input that can change the analysis prompt or its code.

    The prompt text carries the route, skill, app context, truncation marker, probe
    summary, hint facts and Graphify connections. The schema is hashed separately so a
    schema change invalidates a saved answer even when the prompt wording is unchanged.
    Slice bytes are included because the prompt tells the analyzer to read those files.

    Args:
        workspace: The workspace.
        request: The analysis request.

    Returns:
        A SHA-256 hex digest for the prompt identity and all files it reads.
    """
    identity = {
        "prompt_version": PROMPT_VERSION,
        "schema_name": "page-analysis",
        "schema": schema_for_claude("page-analysis"),
        "prompt": add_schema_to_prompt(build_analysis_prompt(request), "page-analysis"),
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    )
    for relative in request.slice_files:
        path = workspace.root / relative
        digest.update(f"\0{relative}\0".encode())
        if path.is_file():
            digest.update(b"present\0")
            digest.update(path.read_bytes())
        else:
            digest.update(b"missing\0")
        digest.update(b"\0")
    return FINGERPRINT_SCHEME + digest.hexdigest()


def find_reusable_analysis(
    folder: Path, fingerprint: str, newest_source: float | None = None
) -> dict[str, Any] | None:
    """Return the saved analysis when it was made from the current request inputs.

    It is reusable when skillgen recorded it for this fingerprint; when it was written
    after the last request and that request had this fingerprint (the agent running
    skillgen answered the prompt it was handed); or, for an analysis with no versioned
    record, when it is newer than every file it reads.

    Args:
        folder: The route's page folder.
        fingerprint: The current request's fingerprint.
        newest_source: When the newest slice file last changed, if there are any.

    Returns:
        The validated analysis, or None when it must be made again.

    Raises:
        AnalysisError: If an analysis written for this request does not fit the schema.
    """
    analysis = folder / ANALYSIS_FILE
    if not analysis.is_file():
        return None
    if _read_fingerprint(folder / ANALYSIS_FINGERPRINT) == fingerprint:
        return check_analysis(read_analysis_file(analysis), str(analysis))
    written = analysis.stat().st_mtime
    request = folder / REQUEST_FINGERPRINT
    is_answer = _read_fingerprint(request) == fingerprint and written > request.stat().st_mtime
    recorded = _read_fingerprint(folder / ANALYSIS_FINGERPRINT)
    # A versioned digest from an older scheme cannot prove that the new prompt inputs match.
    is_unrecorded_but_current = (
        (not recorded or ":" not in recorded)
        and newest_source is not None
        and written > newest_source
    )
    if not is_answer and not is_unrecorded_but_current:
        return None
    document = check_analysis(read_analysis_file(analysis), str(analysis))
    write_text_atomically(folder / ANALYSIS_FINGERPRINT, fingerprint)
    return document


def find_newest_source(workspace: Workspace, request: AnalysisRequest) -> float | None:
    """Return when the newest of a request's slice files last changed, or None."""
    times = [
        (workspace.root / relative).stat().st_mtime
        for relative in request.slice_files
        if (workspace.root / relative).is_file()
    ]
    return max(times) if times else None


def _read_fingerprint(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def finish_route(
    workspace: Workspace,
    settings: Settings,
    entry: RouteEntry,
    analysis: dict[str, Any],
    options: GenerateOptions,
) -> RouteOutcome:
    """Merge, check and write one analysed route. Run routes one at a time.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entry: The route.
        analysis: Its page analysis.
        options: Probe and description.

    Returns:
        What happened.
    """
    has_form = bool(analysis.get("has_form", True) and analysis.get("fields"))
    mark_has_form(workspace, entry.route, has_form=has_form)
    if not has_form:
        return RouteOutcome(entry.route, entry.skill, "no-form")
    return write_skill(workspace, settings, entry, analysis, options)


def generate_route(
    workspace: Workspace, settings: Settings, entry: RouteEntry, options: GenerateOptions
) -> RouteOutcome:
    """Run the whole pipeline for one route.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entry: The route.
        options: Analyzer, probe and description.

    Returns:
        What happened.

    Raises:
        AnalysisError: If the analysis fails.
    """
    analysis = analyze_route(workspace, settings, entry, options)
    return finish_route(workspace, settings, entry, analysis, options)


def generate_url(
    workspace: Workspace,
    settings: Settings,
    entry: RouteEntry,
    probe: ProbedPage,
    description: str = "",
) -> RouteOutcome:
    """Generate from observed page facts, skipping every source-code step.

    Args:
        workspace: The output workspace, which need not contain source code.
        settings: Settings with this URL's origin.
        entry: The concrete page route and chosen skill name.
        probe: The read-only browser capture.
        description: Optional skill description.

    Returns:
        The shared writer's outcome, or no-form when nothing usable was observed.
    """
    from skillgen.probe.capture import probed_page_to_dict  # noqa: PLC0415

    if not any(f.is_visible and not f.is_repeated for f in probe.fields):
        return RouteOutcome(entry.route, entry.skill, "no-form")
    write_json(
        workspace.page_folder(entry.skill) / "probe" / "probe.json", probed_page_to_dict(probe)
    )
    return write_skill(
        workspace,
        settings,
        entry,
        {},
        GenerateOptions(probe=probe, description=description, is_url_mode=True),
    )


def write_skill(
    workspace: Workspace,
    settings: Settings,
    entry: RouteEntry,
    analysis: dict[str, object],
    options: GenerateOptions,
) -> RouteOutcome:
    """Merge and check one route, then write its page model and skill folder.

    Nothing but the questions is saved until every check passes, so a failed run leaves
    the skill and its `page.json` as they were. Answering a question can fix a failed
    check, so the questions are saved either way.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entry: The route.
        analysis: The validated page analysis.
        options: Probe and description.

    Returns:
        What happened.
    """
    old_questions = workspace.read_questions()
    merged = merge_analysis(
        workspace,
        settings,
        entry,
        analysis,
        old_questions,
        page_facts=options.probe if options.is_url_mode else None,
    )
    if options.is_url_mode:
        # A read-only pass cannot prove filling, even when no fields are required.
        merged = replace(merged, page=replace(merged.page, is_verified=False))
    previous = workspace.read_page(entry.skill)
    # The developer's own steps (--open, routes.json) win over the code analysis's.
    opened = replace(merged.page, open_steps=entry.open_steps or merged.page.open_steps)
    measured = measure_page_model(previous, opened, analysis, options)
    need = measured.need
    page = replace(measured.page, version=next_version(previous, measured.page))
    raised = [q for q in merged.questions if q.subject not in measured.proven]
    questions = merge_questions(old_questions, entry.skill, raised)
    workspace.write_questions(questions)
    open_count = sum(1 for q in questions if q.skill == entry.skill and not q.answer)
    folder = workspace.skills_folder(settings) / entry.skill
    files = build_files_for(workspace, page, folder, options.description)
    problems = find_skill_problems(page, files, entry.skill)
    logger.info(
        "%s: %d field(s) kept of %d analysed, %d open question(s), verified=%s",
        entry.route,
        len(page.fields),
        len(list(analysis.get("fields") or [])),  # type: ignore[call-overload]
        open_count,
        page.is_verified,
    )
    if problems:
        return RouteOutcome(entry.route, entry.skill, "invalid", tuple(problems), open_count)
    save_page(workspace, previous, page, merged)
    workspace.write_skill_files(folder, files)
    return RouteOutcome(
        entry.route,
        entry.skill,
        "written",
        measured.notes
        + tuple(find_size_notes(files[SKILL_FILE]))
        + tuple(describe_live_page_gaps(workspace, entry.skill, page))
        + ((str(need),) if need else ()),
        open_count,
        folder.relative_to(workspace.root).as_posix(),
        page.is_verified,
        len(page.layout.boxes) if page.layout else 0,
        need.need if need else None,
        need.detail if need else "",
    )


def merge_analysis(
    workspace: Workspace,
    settings: Settings,
    entry: RouteEntry,
    analysis: dict[str, object],
    old_questions: Sequence[Question],
    *,
    page_facts: ProbedPage | None = None,
) -> MergeResult:
    """Build a route's page model from its analysis, with the developer's answers.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entry: The route.
        analysis: The validated page analysis.
        old_questions: Every saved question, for the answers already given.
        page_facts: Read-only URL observations; absent in code mode.

    Returns:
        The merged page, its questions and evidence.
    """
    answers = {q.subject: q.answer for q in old_questions if q.skill == entry.skill and q.answer}
    return build_page_model(
        MergeInput(
            route=entry.route,
            skill=entry.skill,
            analysis=analysis,
            app_name=settings.app_name,
            app_url=settings.app_url,
            # Code mode supplies no page facts, so its `--xy` still only adds layout.
            probe=page_facts,
            answers=answers,
            source_commit="" if page_facts is not None else read_source_commit(workspace.root),
        )
    )


@dataclass(frozen=True)
class MeasuredPage:
    """A code-built page after `--xy`, or after keeping an earlier run's x/y.

    Attributes:
        page: The page, with the open steps that worked and its layout.
        need: What the developer must do before x/y can be measured, if anything.
        proven: Question subjects the browser settled (`open`, `views`): what the code
            only deduced was shown to work.
        notes: Sentences about the x/y for the run's report.
    """

    page: PageModel
    need: ActionNeededError | None = None
    proven: frozenset[str] = frozenset()
    notes: tuple[str, ...] = ()


def measure_page_model(
    previous: PageModel | None,
    page: PageModel,
    analysis: dict[str, Any],
    options: GenerateOptions,
) -> MeasuredPage:
    """Measure x/y, recovering what can be recovered without the developer.

    When no field shows, the analysis's open steps are tried even when they were only
    deduced: fields appearing proves them. When nothing could be measured, the earlier
    run's x/y is kept for unchanged fields rather than thrown away.

    Args:
        previous: The page model before this run, if any.
        page: The code-built page, with the developer's or the trusted open steps.
        analysis: The page analysis, for open steps worth trying.
        options: The measurer or a saved capture.

    Returns:
        The page with its layout, and what is still needed.
    """
    trial = with_view_candidates(page, analysis, options)
    layout, need = measure_layout_safely(trial, options)
    proven: set[str] = set()
    candidates = () if page.open_steps else find_open_candidates(analysis)
    if need is not None and need.need is Need.OPEN and candidates:
        tried = replace(trial, open_steps=candidates)
        retried, retry_need = measure_layout_safely(tried, options)
        if retried is not None:
            logger.info("%s: the code's open steps showed the form", page.route)
            trial, layout, need = tried, retried, None
            page = replace(page, open_steps=candidates)
            proven.add("open")
        elif retry_need is not None and retry_need.need is not Need.OPEN:
            need = retry_need
    page, has_all_views = keep_proven_views(page, trial, layout)
    if has_all_views:
        proven.add("views")
    could_not_measure = options.measure_layout is None or need is not None
    carried = carry_layout(previous, page) if layout is None and could_not_measure else None
    notes = describe_layout_notes(previous, layout, carried)
    return MeasuredPage(replace(page, layout=layout or carried), need, frozenset(proven), notes)


def with_view_candidates(
    page: PageModel, analysis: dict[str, Any], options: GenerateOptions
) -> PageModel:
    """Under `--xy`, walk every view the code names, deduced ones too, to prove them.

    Args:
        page: The code-built page, with its trusted views.
        analysis: The page analysis.
        options: The run's options; without a measurer nothing is walked.

    Returns:
        The page with every walkable view, or the page as it was.
    """
    if options.measure_layout is None:
        return page
    candidates = find_view_candidates(analysis, {spec.key for spec in page.fields})
    return replace(page, views=candidates) if len(candidates) > len(page.views) else page


def keep_proven_views(
    page: PageModel, trial: PageModel, layout: Layout | None
) -> tuple[PageModel, bool]:
    """Keep the trusted views and every walked view whose fields appeared, in order.

    Views are reached one from another, so the list stops at the first view that was
    neither trusted nor seen.

    Args:
        page: The page with its trusted views.
        trial: The page as it was walked.
        layout: What the walk measured.

    Returns:
        The page with its views, and True when every walked view was kept.
    """
    if layout is None or trial.views == page.views:
        return page, False
    trusted = {view.name for view in page.views}
    measured = {key for key, _ in layout.boxes}
    kept: list[View] = []
    for view in trial.views:
        if view.name not in trusted and not measured & set(view.keys):
            break
        kept.append(view)
    if len(kept) > len(page.views):
        logger.info("%s: %d view(s) shown in the browser", page.route, len(kept))
    return replace(page, views=tuple(kept)), len(kept) == len(trial.views)


def measure_layout_safely(
    page: PageModel, options: GenerateOptions
) -> tuple[Layout | None, ActionNeededError | None]:
    """Measure x/y for `--xy`, or take it from a saved capture.

    Args:
        page: The code-built page, with its open steps.
        options: The measurer or the capture.

    Returns:
        The layout, or None; and what the developer must do first, when the measuring
        stopped at a login, a stopped server or a missing browser.
    """
    if options.measure_layout is None:
        return build_layout(page.fields, options.probe), None
    try:
        return options.measure_layout(page), None
    except ActionNeededError as error:
        # x/y only ever adds: the skill is written from the code and the need reported.
        logger.warning("x/y not measured for %s: %s", page.route, error)
        return None, error


def build_files_for(
    workspace: Workspace, page: PageModel, folder: Path, description: str
) -> dict[str, str]:
    """Build a skill's files, keeping the user section of the skill already there.

    Args:
        workspace: The workspace, for the global rules.
        page: The page model.
        folder: The skill folder.
        description: A developer-chosen description.

    Returns:
        Relative path to file text.
    """
    skill_file = folder / SKILL_FILE
    old_skill = skill_file.read_text(encoding="utf-8") if skill_file.exists() else ""
    return build_skill_files(
        page,
        read_fill_engine(),
        extract_user_block(old_skill),
        workspace.read_global_rules(),
        description,
    )


def describe_live_page_gaps(workspace: Workspace, skill: str, page: PageModel) -> list[str]:
    """Say what the live page offered that the code reading did not account for.

    The fields and the parts behind a click come from the code; the browser only
    replays what that reading found. Anything it missed is never opened and never
    reaches the skill, so the saved inventory is compared against the model and the
    difference is reported rather than left silent.

    Args:
        workspace: The workspace.
        skill: The skill name, which names the saved probe capture.
        page: The model built from the code.

    Returns:
        One line per finding; empty when there is no capture or nothing was missed.
    """
    probe = read_probe_capture(workspace, skill)
    if probe is None:
        return []
    return describe_missed(find_missed_on_page(page, probe))


def find_skill_problems(page: PageModel, files: dict[str, str], skill: str) -> list[str]:
    """Run every check on a page model and its skill files.

    Args:
        page: The page model.
        files: The skill's files.
        skill: The skill name.

    Returns:
        One sentence per failed check; empty when the skill may be written.
    """
    problems = check_page_model(page) + check_skill_files(files, skill)
    problems += [
        f"{f.path}:{f.line}: looks like a {f.kind} ({f.excerpt})" for f in scan_files(files)
    ]
    for problem in problems:
        logger.warning("%s: %s", skill, problem)
    return problems


def save_page(
    workspace: Workspace, previous: PageModel | None, page: PageModel, merged: MergeResult
) -> None:
    """Save a checked page model, what changed since the last one, and its evidence.

    Args:
        workspace: The workspace.
        previous: The page model before this run, if any.
        page: The page model to save.
        merged: The merge result, for the evidence.
    """
    workspace.write_page(page)
    if previous is not None:
        changes = [
            {"kind": c.kind, "subject": c.subject, "detail": c.detail}
            for c in diff_pages(previous, page)
        ]
        write_json(
            workspace.page_folder(page.skill) / "changes.json",
            {"version": page.version, "changes": changes},
        )
    workspace.write_evidence(page.skill, merged.evidence)


def describe_layout_notes(
    previous: PageModel | None, measured: Layout | None, carried: Layout | None
) -> tuple[str, ...]:
    """Say what happened to x/y when this run did not measure it, so nothing is unseen.

    Args:
        previous: The page model before this run, if any.
        measured: The layout this run measured, if any.
        carried: The earlier layout kept instead, if any.

    Returns:
        One sentence, or nothing when x/y was measured or there never was any.
    """
    if carried is not None:
        return (
            f"x/y kept from the last --xy run for {len(carried.boxes)} field(s) whose "
            "selector did not change; add --xy to measure it again",
        )
    if measured is None and previous is not None and previous.layout is not None:
        return ("x/y from the last --xy run was dropped: no field kept its selector",)
    return ()


def mark_has_form(workspace: Workspace, route: str, *, has_form: bool) -> None:
    """Record in `routes.json` whether a route has a form.

    Args:
        workspace: The workspace.
        route: The route.
        has_form: What the analysis found.
    """
    table = workspace.read_routes()
    entries = tuple(replace(e, has_form=has_form) if e.route == route else e for e in table.entries)
    workspace.write_routes(RouteTable(entries))


def try_load_graph(workspace: Workspace) -> CodeGraph | None:
    """Load the code graph, or None (with a warning) when Graphify cannot run.

    Args:
        workspace: The workspace.

    Returns:
        The graph, or None.
    """
    try:
        return load_graph(workspace)
    except GraphError as error:
        logger.warning("continuing without a code graph: %s", error)
        return None


def probe_for_route(
    workspace: Workspace, settings: Settings, entry: RouteEntry
) -> ProbedPage | None:
    """Return the saved capture when it is evidence about this route's page.

    A capture is only evidence about the page it was taken on: one from another route,
    or from a sign-in page that stood in for this one, would steer the analysis wrong.
    So its URL is checked against the route before it is used, and an empty capture is
    treated as no evidence at all.

    Args:
        workspace: The workspace.
        settings: Project settings, for the app URL.
        entry: The route being analysed.

    Returns:
        The capture, or None.
    """
    probe = read_probe_capture(workspace, entry.skill)
    if probe is None or not probe.fields:
        return None
    wanted = urlparse(settings.app_url.rstrip("/") + entry.route).path.rstrip("/")
    seen = urlparse(probe.url).path.rstrip("/")
    if wanted and seen != wanted:
        logger.info("%s: ignoring a capture taken at %s", entry.route, probe.url)
        return None
    return probe


def read_probe_capture(workspace: Workspace, skill: str) -> ProbedPage | None:
    """Read a saved probe result for a skill, if one exists.

    Args:
        workspace: The workspace.
        skill: The skill name.

    Returns:
        The probe result, or None.
    """
    path = workspace.page_folder(skill) / "probe" / "probe.json"
    if not path.exists():
        return None
    from skillgen.probe.capture import probed_page_from_dict  # noqa: PLC0415 - probe stays optional

    try:
        return probed_page_from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, KeyError) as error:
        raise ProbeError(f"{path} is not a valid probe capture: {error}") from error


def read_changed_skills(workspace: Workspace, skills: Iterable[str]) -> list[str]:
    """List skills whose last regeneration changed their page model.

    Args:
        workspace: The workspace.
        skills: Skill names.

    Returns:
        Skills with a non-empty `changes.json`.
    """
    changed = []
    for skill in skills:
        path = workspace.page_folder(skill) / "changes.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("changes"):
            changed.append(skill)
    return changed


def write_index(
    workspace: Workspace, settings: Settings, generated_on: str
) -> tuple[Path, Path, dict[str, Any]]:
    """Write `skills-index.json` and `skills-index.html` at the repository root.

    Args:
        workspace: The workspace.
        settings: Project settings.
        generated_on: The date to show, ISO format.

    Returns:
        (html path, json path, the index document).
    """
    table = workspace.read_routes()
    skills_root = workspace.skills_folder(settings)
    pages = [
        page
        for e in table.entries
        if (page := workspace.read_page(e.skill)) and (skills_root / e.skill).is_dir()
    ]
    sizes = {
        page.skill: len((skills_root / page.skill / SKILL_FILE).read_text(encoding="utf-8"))
        for page in pages
        if (skills_root / page.skill / SKILL_FILE).exists()
    }
    detected = sorted(
        {source.split(":", 1)[1] for e in table.entries for source in e.sources if ":" in source}
    )
    document = build_index_data(
        IndexInput(
            app_name=settings.app_name,
            pages=tuple(pages),
            routes=table.entries,
            skill_sizes=sizes,
            commit=read_source_commit(workspace.root),
            generated_on=generated_on,
            detected=tuple(detected),
            changed=tuple(read_changed_skills(workspace, [page.skill for page in pages])),
        )
    )
    json_path, html_path = (
        workspace.root / "skills-index.json",
        workspace.root / "skills-index.html",
    )
    write_json(json_path, document)
    write_text_atomically(html_path, render_index_html(document, read_index_template()))
    return html_path, json_path, document


def ask_claude_for_routes(
    workspace: Workspace, settings: Settings, graph: CodeGraph | None, known: Iterable[str]
) -> list[RouteCandidate]:
    """Let Claude Code list routes from a map of the code graph's likely router files.

    Args:
        workspace: The workspace.
        settings: Project settings.
        graph: The code graph; without one Claude starts from the entry points.
        known: Routes already found, so Claude adds only missing ones.

    Returns:
        Candidates with source `claude`, limited to files that exist.

    Raises:
        AnalysisError: If Claude Code fails.
    """
    hints = rank_router_candidates(graph) if graph else []
    prompt = build_route_listing_prompt(
        settings.app_name, [(h.file, h.links, h.reasons) for h in hints], sorted(set(known))
    )
    write_text_atomically(workspace.folder / "route-listing-prompt.md", prompt + "\n")
    listed = list_routes_with_claude(workspace.root, prompt)
    candidates = []
    for item in listed:
        files = tuple(f for f in item.get("entry_files", []) if (workspace.root / f).is_file())
        candidates.append(
            RouteCandidate(str(item["route"]), "claude", files, str(item.get("title", "")))
        )
    return candidates
