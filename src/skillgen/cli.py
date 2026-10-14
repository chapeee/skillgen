"""Command-line interface. The only module that prints.

Every command supports `--json`; its output is validated against
`schema/cli/<command>.schema.json` before it is printed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from skillgen import TOOL_NAME, __version__
from skillgen.analyze.runner import (
    Analyzer,
    ClaudeCodeAnalyzer,
    FileAnalyzer,
    ReplayAnalyzer,
    is_limit_reached,
)
from skillgen.assets import find_data_folder
from skillgen.config import AnalyzerKind, Environment, Settings, check_app_url, update_settings
from skillgen.drift.check import find_drift, list_changed_files
from skillgen.errors import (
    ActionNeededError,
    AnalysisError,
    ConfigError,
    GraphError,
    Need,
    RuleError,
    SkillgenError,
    WorkspaceError,
)
from skillgen.export import export_chatgpt_plugin, export_skills
from skillgen.generate.folder import SKILL_FILE
from skillgen.generate.user_rules import USER_END, USER_START, append_user_rule, extract_user_block
from skillgen.graph.codegraph import CodeGraph
from skillgen.graph.connections import GraphifyGraph
from skillgen.handoff import OVERWRITE, NextStep, build_next_step
from skillgen.logs import list_logs, start_logging, stop_logging
from skillgen.model.page import Layout, PageModel
from skillgen.model.route import RouteCandidate, RouteEntry, RouteTable
from skillgen.pipeline import (
    GenerateOptions,
    RouteOutcome,
    analyze_route,
    apply_open_steps,
    apply_prefix,
    apply_skill_name,
    ask_claude_for_routes,
    choose_prefix,
    discover_routes,
    ensure_route,
    find_route_candidates,
    finish_route,
    generate_route,
    generate_url,
    generated_paths,
    load_graph,
    load_graphify_graph,
    prepare_route,
    probe_for_route,
    refresh_entry_files,
    restore_skill_names,
    try_load_graph,
    write_index,
)
from skillgen.routes.astgrep import find_ast_grep
from skillgen.routes.naming import is_valid_name
from skillgen.routes.paths import is_route_wanted, normalize_route
from skillgen.schema import find_schema_problems
from skillgen.validate.scan import scan_files
from skillgen.validate.spec import check_skill_files, find_size_notes
from skillgen.workspace import (
    WORKSPACE_DIR,
    Workspace,
    find_workspace_root,
)

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_ERROR = 2
# The run stopped at something whoever runs it does next; see each result's `next`.
EXIT_NEEDS = 3


@dataclass
class Reply:
    """What a command reports: JSON data and the human-readable lines.

    Attributes:
        data: The `--json` payload, without `ok` and `command`.
        lines: Text printed without `--json`.
        is_ok: False when the command ran but something failed.
        needs_action: True when the run waits for a next step (exit code 3).
    """

    data: dict[str, Any] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    is_ok: bool = True
    needs_action: bool = False


def open_workspace(arguments: argparse.Namespace) -> Workspace:
    """Find the workspace for the current folder or `--root`.

    Args:
        arguments: Parsed arguments.

    Returns:
        The workspace.

    Raises:
        WorkspaceError: If none exists.
    """
    start = Path(arguments.root or ".").resolve()
    root = find_workspace_root(start)
    if root is None:
        raise WorkspaceError(f"no .{TOOL_NAME}/ workspace here; run `{TOOL_NAME} init` first")
    return Workspace(root)


def command_init(arguments: argparse.Namespace) -> Reply:
    """Create `.skillgen/` with its config."""
    workspace = Workspace(Path(arguments.root or ".").resolve())
    is_new = not workspace.exists()
    settings = workspace.read_settings() if not is_new else Settings(app_name=workspace.root.name)
    changes: dict[str, Any] = {}
    if arguments.app_name:
        changes["app_name"] = arguments.app_name
    if arguments.url:
        changes |= {"app_url": arguments.url, "should_probe": True}
    if arguments.environment:
        changes["environment"] = Environment(arguments.environment)
    if arguments.name:
        changes["name_prefix"] = arguments.name
    if arguments.analyzer:
        changes["analyzer"] = AnalyzerKind(arguments.analyzer)
    settings = update_settings(settings, **changes)
    workspace.create(settings)
    verb = "Created" if is_new else "Updated"
    return Reply(
        {
            "root": str(workspace.root),
            "config": str(workspace.config_path),
            "app_name": settings.app_name,
            "app_url": settings.app_url,
            "is_new": is_new,
        },
        [
            f"{verb} {workspace.config_path}",
            f"App: {settings.app_name}  URL: {settings.app_url or '(code only)'}",
        ],
    )


def _route_data(entry: RouteEntry) -> dict[str, Any]:
    return {
        "route": entry.route,
        "skill": entry.skill,
        "title": entry.title,
        "sources": list(entry.sources),
        "entry_files": list(entry.entry_files),
        "has_form": entry.has_form,
        "skip": entry.is_skipped,
    }


def command_routes(arguments: argparse.Namespace) -> Reply:
    """Find routes and write `routes.json`; Claude fills gaps from the code graph."""
    workspace = open_workspace(arguments)
    settings = _with_filters(workspace.read_settings(), arguments)
    graph = None if arguments.no_graph else try_load_graph(workspace)
    table = discover_routes(
        workspace,
        settings,
        extra_routes=arguments.route or [],
        prefix=arguments.name or "",
        graph=graph,
    )
    notes: list[str] = []
    should_ask = arguments.ask_claude or (not table.entries and not arguments.no_claude)
    if should_ask:
        notes += _add_claude_routes(workspace, settings, graph, arguments)
        table = workspace.read_routes()
    entries = [
        e for e in table.entries if is_route_wanted(e.route, settings.include, settings.exclude)
    ]
    lines = [f"{len(entries)} route(s) in {workspace.routes_path}", *notes]
    lines += [
        f"  {e.route:<36} {e.skill:<40} {', '.join(e.sources) or 'routes.json'}" for e in entries
    ]
    if not entries:
        lines.append(
            f"No routes found. Name one with `{TOOL_NAME} routes --route /path` or ask Claude Code."
        )
        if find_ast_grep() is None:
            lines.append(
                "ast-grep is not installed, so routes declared in code (React Router, Express, "
                "Flask, Rails, Spring, Laravel...) were not searched; reinstall "
                f"{TOOL_NAME}, which installs it."
            )
    data = {
        "routes": [_route_data(e) for e in entries],
        "count": len(entries),
        "found": len(table.entries),
    }
    return Reply(data, lines)


def _add_claude_routes(
    workspace: Workspace, settings: Settings, graph: Any, arguments: argparse.Namespace
) -> list[str]:
    """Ask Claude Code for routes the probes missed and merge them; return notes."""
    known = [entry.route for entry in workspace.read_routes().entries]
    try:
        candidates = ask_claude_for_routes(workspace, settings, graph, known)
    except AnalysisError as error:
        return [f"Claude Code could not list routes: {error}"]
    discover_routes(
        workspace,
        settings,
        extra_routes=[],
        prefix=arguments.name or "",
        graph=graph,
        extra_candidates=candidates,
    )
    return [
        f"Claude Code listed {len(candidates)} route(s) from the code graph's likely router files."
    ]


def _with_filters(settings: Settings, arguments: argparse.Namespace) -> Settings:
    include = tuple(getattr(arguments, "include", None) or ()) or settings.include
    exclude = tuple(getattr(arguments, "exclude", None) or ()) or settings.exclude
    return replace(settings, include=include, exclude=exclude)


def command_prepare(arguments: argparse.Namespace) -> Reply:
    """Write the slice and prompt for one route, for Claude Code to analyse itself."""
    workspace = open_workspace(arguments)
    settings = workspace.read_settings()
    routes_before = read_routes_text(workspace)
    graph = None if arguments.no_graph else try_load_graph(workspace)
    graphify_graph = try_load_graphify_graph(workspace, graph) if graph is not None else None
    entry = _named_entry(workspace, settings, arguments.route, arguments.name, graph)
    skill_folder = workspace.skills_folder(settings) / entry.skill
    has_skill = bool(find_existing_skills(workspace, settings, [entry]))
    if has_skill and routes_before is not None:
        # The developer has not yet agreed to recreate it, so a rename must not stick.
        restore_skill_names(workspace, routes_before)
    request = prepare_route(
        workspace,
        settings,
        entry,
        graph,
        probe_for_route(workspace, settings, entry),
        graphify_graph=graphify_graph,
        should_load_graphify=False,
    )
    folder = workspace.page_folder(entry.skill)
    schema_path = find_schema_file("page-analysis")
    prompt = (folder / "prompt.md").read_text(encoding="utf-8")
    data = {
        "route": entry.route,
        "skill": entry.skill,
        "skill_exists": has_skill,
        "skill_folder": str(skill_folder),
        "prompt": prompt,
        "prompt_path": str(folder / "prompt.md"),
        "schema_path": str(schema_path),
        "analysis_path": str(folder / "analysis.json"),
        "slice": list(request.slice_files),
    }
    lines = [f"Route {entry.route} → skill {entry.skill}"]
    if has_skill:
        lines.append(
            f"{entry.skill} already exists at {skill_folder}. Ask the developer whether to "
            "recreate and overwrite it before analysing; generate needs --overwrite."
        )
    lines += [
        f"Prompt: {folder / 'prompt.md'}",
        f"Schema: {schema_path}",
        f"Write the analysis to: {folder / 'analysis.json'}",
        f"Then run: {TOOL_NAME} generate --route {entry.route} --analyzer file"
        + (" --overwrite" if has_skill else ""),
    ]
    return Reply(data, lines)


def find_schema_file(name: str) -> Path:
    """Return the path of a shipped schema file.

    Args:
        name: Schema name without suffix.

    Returns:
        The path.
    """
    return Path(__file__).resolve().parent / "schema" / f"{name}.schema.json"


def _named_entry(
    workspace: Workspace,
    settings: Settings,
    route: str,
    name: str | None,
    graph: Any = None,
    *,
    route_candidates: Sequence[RouteCandidate] | None = None,
) -> RouteEntry:
    entry = ensure_route(
        workspace,
        settings,
        normalize_route(route) if route.startswith("/") else route,
        graph,
        route_candidates=route_candidates,
    )
    if name:
        table = apply_skill_name(workspace, workspace.read_routes(), entry.route, name)
        found = table.find(entry.route)
        assert found is not None
        return found
    return entry


def make_analyzer(kind: AnalyzerKind, workspace: Workspace, replay_folder: str | None) -> Analyzer:
    """Build the analyzer a run asked for.

    Args:
        kind: Which analyzer.
        workspace: The workspace.
        replay_folder: Folder of recorded analyses for `replay`.

    Returns:
        The analyzer.

    Raises:
        ConfigError: If `replay` is chosen without a folder.
    """
    if kind is AnalyzerKind.FILE:
        return FileAnalyzer(workspace.folder / "pages")
    if kind is AnalyzerKind.REPLAY:
        if not replay_folder:
            raise ConfigError("--analyzer replay needs --replay-dir")
        return ReplayAnalyzer(Path(replay_folder).resolve())
    return ClaudeCodeAnalyzer(workspace.root)


def _select_entries(
    workspace: Workspace,
    settings: Settings,
    arguments: argparse.Namespace,
    graph: Any = None,
    route_candidates: Sequence[RouteCandidate] | None = None,
) -> list[RouteEntry]:
    if not arguments.all:
        return [
            _named_entry(
                workspace,
                settings,
                arguments.route,
                arguments.name,
                graph,
                route_candidates=route_candidates,
            )
        ]
    if arguments.name:
        apply_prefix(workspace, settings, arguments.name)
    table = workspace.read_routes()
    if not table.entries:
        table = discover_routes(
            workspace,
            settings,
            prefix=arguments.name or "",
            graph=graph,
            route_candidates=route_candidates,
        )
    chosen = [
        entry
        for entry in table.entries
        if not entry.is_skipped
        and (entry.has_form is not False or arguments.force)
        and is_route_wanted(entry.route, settings.include, settings.exclude)
    ]
    return refresh_entry_files(
        workspace, settings, chosen, graph, route_candidates=route_candidates
    )


def _settings_for_run(workspace: Workspace, arguments: argparse.Namespace) -> Settings:
    settings = _with_filters(workspace.read_settings(), arguments)
    if arguments.url:
        settings = update_settings(
            settings, app_url=arguments.url, should_probe=not arguments.code_only
        )
        workspace.write_settings(
            replace(
                settings,
                include=workspace.read_settings().include,
                exclude=workspace.read_settings().exclude,
            )
        )
    # The command alone decides: `probe` in config.json no longer opens a browser, so a
    # plain run is always code only.
    wants_xy = bool(getattr(arguments, "xy", False) or arguments.url)
    return replace(settings, should_probe=wants_xy and not arguments.code_only)


def _analyze_all(
    workspace: Workspace,
    settings: Settings,
    entries: Sequence[RouteEntry],
    options_for: Callable[[RouteEntry], GenerateOptions],
    concurrency: int,
) -> list[tuple[RouteEntry, dict[str, Any] | SkillgenError]]:
    """Analyse routes in parallel; the error replaces a failed analysis."""

    def run(entry: RouteEntry) -> tuple[RouteEntry, dict[str, Any] | SkillgenError]:
        try:
            return entry, analyze_route(workspace, settings, entry, options_for(entry))
        except SkillgenError as error:
            return entry, error

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        return list(pool.map(run, entries))


def _outcome_data(outcome: RouteOutcome, step: NextStep | None) -> dict[str, Any]:
    data = {
        "route": outcome.route,
        "skill": outcome.skill,
        "status": outcome.status,
        "problems": list(outcome.problems),
        "open_questions": outcome.open_questions,
        "skill_folder": outcome.skill_folder,
        "verified": outcome.is_verified,
        "measured_fields": outcome.measured_fields,
    }
    if step is not None:
        data["next"] = {
            "action": step.action,
            "need": step.need,
            "reason": step.reason,
            "ask": step.ask,
            "run": step.run,
            "then": step.then,
            "prompt": step.prompt,
            "write": step.write,
        }
    return data


def describe_next_step(
    workspace: Workspace, outcome: RouteOutcome, command_line: Sequence[str]
) -> NextStep | None:
    """Say what whoever runs skillgen does next for one route, if anything.

    Args:
        workspace: The workspace, for the analysis prompt's paths.
        outcome: What happened to the route.
        command_line: The arguments of this run.

    Returns:
        The next step, or None when the route needs nothing more.
    """
    if outcome.status == "exists":
        return build_next_step(OVERWRITE, outcome.skill, command_line)
    if outcome.need is None:
        return None
    folder = workspace.page_folder(outcome.skill)
    return build_next_step(
        outcome.need.value,
        outcome.need_detail,
        command_line,
        has_written=outcome.status == "written",
        prompt=str(folder / "prompt.md"),
        write=str(folder / "analysis.json"),
    )


def finish_analysed(
    workspace: Workspace,
    settings: Settings,
    analysed: Sequence[tuple[RouteEntry, dict[str, Any] | SkillgenError]],
    options_for: Callable[[RouteEntry], GenerateOptions],
    can_hand_over: bool,
) -> list[RouteOutcome]:
    """Write each analysed route; hand a failed analysis to the agent running skillgen.

    The agent running skillgen is itself an AI that can read the code, so when headless
    analysis cannot run (not signed in, a usage limit, not installed) or a written
    analysis is missing or off-schema, the route waits for the agent instead of failing.

    Args:
        workspace: The workspace.
        settings: Settings for this run.
        analysed: Each route with its analysis or the error that replaced it.
        options_for: The generate options of a route.
        can_hand_over: False for recorded analyses, which no agent can redo.

    Returns:
        One outcome per route.
    """
    outcomes = []
    for entry, result in analysed:
        if isinstance(result, AnalysisError) and can_hand_over:
            # A limit resets on its own, so waiting is the cheap answer. Handing the
            # route to the agent instead makes it read the code and write the analysis
            # by hand, which spends much more of the same limit.
            need = Need.LIMIT if is_limit_reached(str(result)) else Need.ANALYSIS
            outcomes.append(
                RouteOutcome(
                    entry.route,
                    entry.skill,
                    "needs",
                    (str(result),),
                    need=need,
                    need_detail=str(result),
                )
            )
        elif isinstance(result, SkillgenError):
            outcomes.append(RouteOutcome(entry.route, entry.skill, "failed", (str(result),)))
        else:
            outcomes.append(finish_route(workspace, settings, entry, result, options_for(entry)))
    return outcomes


def find_existing_skills(
    workspace: Workspace, settings: Settings, entries: Sequence[RouteEntry]
) -> list[RouteEntry]:
    """Return the routes whose skill folder already holds a `SKILL.md`.

    Args:
        workspace: The workspace.
        settings: Project settings, for the skills folder.
        entries: The routes about to be generated.

    Returns:
        The routes whose skill a run would overwrite.
    """
    folder = workspace.skills_folder(settings)
    return [entry for entry in entries if (folder / entry.skill / SKILL_FILE).is_file()]


def hold_existing_skills(
    workspace: Workspace,
    settings: Settings,
    entries: Sequence[RouteEntry],
    should_overwrite: bool,
) -> tuple[list[RouteEntry], list[RouteOutcome]]:
    """Split routes into those to generate and existing skills to leave alone.

    The command never asks on its own: it usually runs inside Claude Code, where there
    is no terminal to answer from. It reports what exists, so whoever runs it can ask
    the developer and run again with `--overwrite`.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entries: The routes selected for this run.
        should_overwrite: Recreate skills that already exist.

    Returns:
        (routes to generate, an `exists` outcome for each skill left alone).
    """
    existing = [] if should_overwrite else find_existing_skills(workspace, settings, entries)
    held = {entry.skill for entry in existing}
    outcomes = [
        RouteOutcome(
            entry.route,
            entry.skill,
            "exists",
            (
                "already exists and was left as it is; ask before recreating it, then run "
                "again with --overwrite (notes in its user section are kept)",
            ),
            skill_folder=str(workspace.skills_folder(settings) / entry.skill),
        )
        for entry in existing
    ]
    return [entry for entry in entries if entry.skill not in held], outcomes


def _with_open_steps(
    workspace: Workspace, entries: list[RouteEntry], arguments: argparse.Namespace
) -> list[RouteEntry]:
    """Save `--open` steps on the one route they belong to.

    Args:
        workspace: The workspace.
        entries: The routes selected for this run.
        arguments: The parsed command line.

    Returns:
        The routes, with the steps applied.

    Raises:
        ConfigError: If `--open` is used without exactly one route.
    """
    if not arguments.open:
        return entries
    if arguments.all or len(entries) != 1:
        raise ConfigError("--open describes one page; use it with --route")
    table = apply_open_steps(workspace, workspace.read_routes(), entries[0].route, arguments.open)
    found = table.find(entries[0].route)
    return [found] if found is not None else entries


def read_routes_text(workspace: Workspace) -> str | None:
    """Read `routes.json` as text, to put it back if a run ends up changing nothing.

    Args:
        workspace: The workspace.

    Returns:
        The file's text, or None when it does not exist yet.
    """
    path = workspace.routes_path
    return path.read_text(encoding="utf-8") if path.is_file() else None


def command_generate_url(arguments: argparse.Namespace) -> Reply:
    """Generate one skill from a URL alone in the chosen output folder."""
    from skillgen.probe.readonly import read_url  # noqa: PLC0415 - optional browser

    if not arguments.url:
        raise ConfigError("a page URL is required")
    check_app_url(arguments.url)
    if not is_valid_name(arguments.name):
        raise ConfigError(
            "skill name must be lowercase words or digits joined by single "
            "hyphens, at most 64 characters"
        )
    workspace = Workspace(Path(arguments.root or ".").resolve())
    settings = workspace.read_settings() if workspace.exists() else Settings()
    parsed = urlsplit(arguments.url)
    route = parsed._replace(scheme="", netloc="", path=parsed.path or "/").geturl()
    entry = RouteEntry(route, arguments.name, sources=("url",), is_name_locked=True)
    entries, held = hold_existing_skills(workspace, settings, [entry], arguments.overwrite)
    if not entries:
        return _generate_reply(workspace, held, arguments.command_line)
    probe = read_url(arguments.url)
    # Redirects define the page actually observed, including its query and fragment.
    final = urlsplit(probe.url)
    origin = f"{final.scheme}://{final.netloc}"
    route = final._replace(scheme="", netloc="", path=final.path or "/").geturl()
    entry = replace(entry, route=route, title=probe.title)
    if not workspace.exists():
        workspace.create(replace(settings, app_name=final.hostname or "", app_url=origin))
        settings = workspace.read_settings()
    outcome = generate_url(
        workspace, replace(settings, app_url=origin), entry, probe, arguments.description or ""
    )
    if outcome.status == "written":
        others = tuple(e for e in workspace.read_routes().entries if e.skill != entry.skill)
        workspace.write_routes(RouteTable((*others, replace(entry, has_form=True))))
    return _generate_reply(workspace, [outcome], arguments.command_line)


def command_generate(arguments: argparse.Namespace) -> Reply:
    """Generate one skill per route."""
    workspace = open_workspace(arguments)
    settings = _settings_for_run(workspace, arguments)
    routes_before = read_routes_text(workspace)
    # The graph is loaded before the routes are chosen: it resolves a route's component
    # to its own file, which is what keeps a page's slice to that page.
    graph = None if arguments.no_graph else try_load_graph(workspace)
    saved_routes = workspace.read_routes()
    saved_entry = saved_routes.find(arguments.route) if not arguments.all else None
    needs_route_candidates = (
        graph is not None
        or (not arguments.all and (saved_entry is None or not saved_entry.entry_files))
        or (arguments.all and not saved_routes.entries)
    )
    route_candidates = (
        find_route_candidates(workspace, settings, graph) if needs_route_candidates else None
    )
    selected = _with_open_steps(
        workspace,
        _select_entries(workspace, settings, arguments, graph, route_candidates),
        arguments,
    )
    entries, held = hold_existing_skills(workspace, settings, selected, arguments.overwrite)
    command_line = arguments.command_line
    if not entries:
        # Choosing routes can rename one (`--name`); a run that writes nothing leaves
        # the names as it found them, but keeps the code files it discovered.
        if routes_before is not None:
            restore_skill_names(workspace, routes_before)
        return _generate_reply(workspace, held, command_line)
    graphify_graph = try_load_graphify_graph(workspace, graph) if graph is not None else None
    # What stops x/y never stops the skill: it is written from the code, and the run
    # then says what to fix so the next run (which reuses the analysis) can measure.
    xy_need = find_xy_need_before_work(settings)
    if xy_need is not None:
        settings = replace(settings, should_probe=False)
    kind = AnalyzerKind(arguments.analyzer or settings.analyzer.value)
    analyzer = make_analyzer(kind, workspace, arguments.replay_dir)

    def options_for(entry: RouteEntry) -> GenerateOptions:
        return GenerateOptions(
            analyzer=analyzer,
            description=arguments.description or "",
            should_save_analysis=not isinstance(analyzer, FileAnalyzer),
            # Recorded analyses are fixed inputs; every other analysis is reused while
            # its prompt and code stay the same, so a rerun picks up where it stopped.
            should_reuse_analysis=kind is not AnalyzerKind.REPLAY,
            graph=graph,
            graphify_graph=graphify_graph,
            should_load_graphify=False,
            measure_layout=_layout_measurer(workspace, settings, entry),
        )

    analysed = _analyze_all(
        workspace, settings, entries, options_for, arguments.concurrency or settings.concurrency
    )
    outcomes = finish_analysed(
        workspace, settings, analysed, options_for, kind is not AnalyzerKind.REPLAY
    )
    if xy_need is not None:
        outcomes = [add_xy_need(outcome, *xy_need) for outcome in outcomes]
    return _generate_reply(workspace, [*held, *outcomes], command_line)


def find_xy_need_before_work(settings: Settings) -> tuple[Need, str] | None:
    """Find what stops `--xy` (no address, no browser, no server) before any work.

    Args:
        settings: Settings for this run.

    Returns:
        What is missing and the URL it is about, or None.
    """
    if not settings.should_probe:
        return None
    from skillgen.probe.runner import find_xy_need  # noqa: PLC0415 - probe is optional

    return find_xy_need(settings)


def add_xy_need(outcome: RouteOutcome, need: Need, detail: str) -> RouteOutcome:
    """Attach what stopped x/y to a skill written from the code alone.

    Args:
        outcome: What happened to the route.
        need: What x/y needs.
        detail: The URL it is about.

    Returns:
        The outcome, with the need when the skill was written and needs nothing else.
    """
    if outcome.status != "written" or outcome.need is not None:
        return outcome
    note = f"x/y not measured yet: {need.value}"
    return replace(outcome, problems=(*outcome.problems, note), need=need, need_detail=detail)


def _layout_measurer(
    workspace: Workspace, settings: Settings, entry: RouteEntry
) -> Callable[[PageModel], Layout | None] | None:
    """Return what measures a route's x/y for `--xy`, or None for a normal run.

    A normal run gets None, so it neither opens a browser nor reads a capture saved by
    an earlier run. A failed measurement leaves the skill as the code built it.

    Args:
        workspace: The workspace.
        settings: Settings for this run; `should_probe` is set by `--xy`.
        entry: The route, with any open steps.

    Returns:
        A function from the code-built page to its layout, or None.
    """
    if not settings.should_probe:
        return None
    if not settings.app_url:
        # `find_xy_need_before_work` turned x/y off for this run; it reports why.
        return None

    def measure(page: PageModel) -> Layout | None:
        try:
            from skillgen.probe.runner import measure_page_layout  # noqa: PLC0415 - optional
        except ImportError:
            logger.warning(
                "x/y skipped: reinstall %s with the probe extra (see the README)", TOOL_NAME
            )
            return None
        try:
            return measure_page_layout(workspace, settings, entry, page)
        except ActionNeededError:
            raise
        except SkillgenError as error:
            logger.warning("x/y skipped for %s: %s", entry.route, error)
            return None

    return measure


def _generate_reply(
    workspace: Workspace, outcomes: Sequence[RouteOutcome], command_line: Sequence[str]
) -> Reply:
    counts = {
        status: sum(1 for o in outcomes if o.status == status)
        for status in ("written", "invalid", "no-form", "failed", "exists")
    }
    # A written skill can still wait for a step, such as signing in to measure x/y.
    counts["needs"] = sum(1 for o in outcomes if o.need is not None)
    steps = [describe_next_step(workspace, o, command_line) for o in outcomes]
    open_questions = sum(o.open_questions for o in outcomes)
    lines = []
    for outcome in outcomes:
        mark = {
            "written": "✓",
            "no-form": "–",
            "invalid": "✗",
            "failed": "✗",
            "exists": "=",
            "needs": "→",
        }[outcome.status]
        detail = outcome.skill_folder or outcome.status
        verified = " (verified)" if outcome.is_verified else ""
        if outcome.measured_fields:
            verified += f" (x/y for {outcome.measured_fields} fields)"
        lines.append(f"{mark} {outcome.route:<32} {outcome.skill:<36} {detail}{verified}")
        lines += [f"    {problem}" for problem in outcome.problems[:8]]
    lines.append(
        f"{counts['written']} written, {counts['no-form']} without a form, "
        f"{counts['invalid'] + counts['failed']} with problems, {open_questions} open question(s)"
        + (f", {counts['exists']} already there" if counts["exists"] else "")
        + (f", {counts['needs']} waiting for a next step" if counts["needs"] else "")
    )
    lines += describe_steps_in_words(outcomes, steps)
    if open_questions:
        lines.append(
            f"See them with `{TOOL_NAME} questions`; "
            f"answer with `{TOOL_NAME} answer <id> <answer>`."
        )
    data = {
        "results": [_outcome_data(o, step) for o, step in zip(outcomes, steps, strict=True)],
        "written": counts["written"],
        "invalid": counts["invalid"],
        "no_form": counts["no-form"],
        "failed": counts["failed"],
        "exists": counts["exists"],
        "needs": counts["needs"],
        "open_questions": open_questions,
    }
    return Reply(
        data,
        lines,
        is_ok=counts["invalid"] + counts["failed"] + counts["needs"] == 0,
        needs_action=counts["needs"] > 0,
    )


def describe_steps_in_words(
    outcomes: Sequence[RouteOutcome], steps: Sequence[NextStep | None]
) -> list[str]:
    """Write each route's next step as lines for the text output.

    Args:
        outcomes: What happened to each route.
        steps: Each route's next step, if any.

    Returns:
        Lines saying what to do next and how to continue.
    """
    lines: list[str] = []
    for outcome, step in zip(outcomes, steps, strict=True):
        if step is None:
            continue
        lines.append(f"Next for {outcome.skill}: {step.reason}.")
        if step.action == "analyse":
            lines.append(f"  Read {step.prompt}, write the page analysis to {step.write},")
        else:
            lines.append(f"  Ask the developer: {step.ask}")
            if step.run:
                lines.append(f"  On yes run: {step.run}")
        lines.append(f"  then run: {step.then}")
    return lines


def command_questions(arguments: argparse.Namespace) -> Reply:
    """List questions for the developer."""
    workspace = open_workspace(arguments)
    questions = [
        q for q in workspace.read_questions() if not arguments.skill or q.skill == arguments.skill
    ]
    shown = questions if arguments.all else [q for q in questions if not q.answer]
    lines = [
        f"{q.id}  [{q.skill}] {q.text}"
        + (f"  (choices: {', '.join(q.choices)})" if q.choices else "")
        + (f"  → {q.answer}" if q.answer else "")
        for q in shown
    ] or ["No open questions."]
    data = {
        "questions": [
            {
                "id": q.id,
                "skill": q.skill,
                "subject": q.subject,
                "text": q.text,
                "choices": list(q.choices),
                "answer": q.answer,
            }
            for q in shown
        ],
        "open": sum(1 for q in questions if not q.answer),
    }
    return Reply(data, lines)


def command_answer(arguments: argparse.Namespace) -> Reply:
    """Record a developer's answer; it applies on the next generate."""
    workspace = open_workspace(arguments)
    questions = workspace.read_questions()
    matches = [q for q in questions if q.id == arguments.id]
    if not matches:
        raise WorkspaceError(
            f"no question {arguments.id!r}; list them with `{TOOL_NAME} questions`"
        )
    target = matches[0]
    workspace.write_questions(
        [replace(q, answer=arguments.answer) if q.id == target.id else q for q in questions]
    )
    lines = [
        f"Answered {target.id}: {arguments.answer}",
        f"Regenerate to apply it: {TOOL_NAME} generate --route {target.skill}",
    ]
    return Reply({"id": target.id, "skill": target.skill, "answer": arguments.answer}, lines)


def command_add_rule(arguments: argparse.Namespace) -> Reply:
    """Add a page rule to a skill's user block, or a global rule."""
    workspace = open_workspace(arguments)
    settings = workspace.read_settings()
    if arguments.is_global:
        path = workspace.global_rules_path
        existing = path.read_text(encoding="utf-8") if path.exists() else "# Rules for all pages\n"
        path.write_text(
            append_user_rule(existing, arguments.rule, arguments.check or "") + "\n",
            encoding="utf-8",
        )
        return Reply(
            {
                "rule": arguments.rule,
                "check": arguments.check or "",
                "global": True,
                "path": str(path),
            },
            [f"Added a global rule to {path}. Regenerate skills to copy it in."],
        )
    if not arguments.skill:
        raise RuleError("name the skill, or pass --global")
    path = workspace.skills_folder(settings) / arguments.skill / SKILL_FILE
    if not path.exists():
        raise RuleError(f"no skill at {path}; generate it first")
    text = path.read_text(encoding="utf-8")
    block = append_user_rule(extract_user_block(text), arguments.rule, arguments.check or "")
    start, end = text.index(USER_START) + len(USER_START), text.index(USER_END)
    path.write_text(text[:start] + "\n" + block + "\n" + text[end:], encoding="utf-8")
    return Reply(
        {
            "skill": arguments.skill,
            "rule": arguments.rule,
            "check": arguments.check or "",
            "global": False,
            "path": str(path),
        },
        [
            f"Added the rule to {path}.",
            f"Regenerate to compile its check into fill.js: "
            f"{TOOL_NAME} generate --route {arguments.skill}",
        ],
    )


def command_validate(arguments: argparse.Namespace) -> Reply:
    """Check skill folders against the spec and scan them for secrets."""
    workspace = open_workspace(arguments)
    skills_root = workspace.skills_folder(workspace.read_settings())
    names = list(arguments.skills)
    if not names and skills_root.exists():
        names = sorted(path.name for path in skills_root.iterdir() if path.is_dir())
    results = []
    for name in names:
        files = workspace.read_skill_files(skills_root / name)
        problems = check_skill_files(files, name)
        problems += [f"{f.path}:{f.line}: looks like a {f.kind}" for f in scan_files(files)]
        notes = find_size_notes(files.get("SKILL.md", ""))
        results.append({"skill": name, "ok": not problems, "problems": problems, "notes": notes})
    lines = [
        f"{'✓' if r['ok'] else '✗'} {r['skill']}"
        + "".join(f"\n    {p}" for p in [*r["problems"], *r["notes"]])
        for r in results
    ]
    return Reply(
        {"results": results},
        lines or ["No skills to validate."],
        is_ok=all(r["ok"] for r in results),
    )


def command_install(arguments: argparse.Namespace) -> Reply:
    """Install the /skillgen command, the route-analyzer agent and the driver skill."""
    target = Path(arguments.target).expanduser() if arguments.target else Path.home() / ".claude"
    source = find_data_folder("claude")
    placements = {
        source / "commands" / "command.md": target / "commands" / f"{TOOL_NAME}.md",
        source / "agents" / "route-analyzer.md": target
        / "agents"
        / f"{TOOL_NAME}-route-analyzer.md",
        source / "skills" / "driver" / "SKILL.md": target / "skills" / TOOL_NAME / "SKILL.md",
    }
    installed = []
    for origin, destination in placements.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = origin.read_text(encoding="utf-8").replace("{{tool}}", TOOL_NAME)
        destination.write_text(text, encoding="utf-8")
        installed.append(str(destination))
    chromium = "chromium skipped (--no-chromium)" if arguments.no_chromium else install_chromium()
    lines = [
        f"Installed into {target}:",
        *[f"  {path}" for path in installed],
        chromium,
        f"In Claude Code, type /{TOOL_NAME} /some/route or /{TOOL_NAME} all.",
    ]
    return Reply({"target": str(target), "installed": installed, "chromium": chromium}, lines)


def install_chromium() -> str:
    """Download Chromium for the probe, if the probe extra is installed.

    Returns:
        What happened, in words.
    """
    if importlib.util.find_spec("playwright") is None:
        return (
            f"chromium skipped: install {TOOL_NAME} with the probe extra to use --xy "
            "(see the README)"
        )
    # Playwright's own installer lives in skillgen's environment, which may not be on PATH.
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    if result.returncode == 0:
        return "chromium installed"
    return f"chromium failed: {result.stderr[-200:]}"


def command_doctor(arguments: argparse.Namespace) -> Reply:
    """Check the tools skillgen uses; with --fix, download Chromium for the probe."""
    fixed: list[str] = []
    if arguments.fix and importlib.util.find_spec("playwright") is not None:
        fixed.append(install_chromium())
    checks = [
        {
            "name": "python",
            "ok": sys.version_info >= (3, 10),
            "detail": sys.version.split()[0],
            "required": True,
        },
        {
            "name": TOOL_NAME,
            "ok": True,
            "detail": f"{__version__} from {Path(__file__).resolve().parent}",
            "required": True,
        },
        _check_import("graphify", "code graph (core)", is_required=True),
        _check_binary("claude", "Claude Code for batch analysis", is_required=False),
        _check_binary(
            "ast-grep",
            f"router hint packs (installed with {TOOL_NAME})",
            is_required=False,
        ),
        _check_import(
            "playwright",
            "runtime probe (probe extra)",
            is_required=False,
        ),
    ]
    lines = [
        f"{'✓' if c['ok'] else ('✗' if c['required'] else '·')} {c['name']:<10} {c['detail']}"
        for c in checks
    ]
    return Reply(
        {"checks": checks, "fixed": fixed},
        [*lines, *fixed],
        is_ok=all(c["ok"] for c in checks if c["required"]),
    )


def _check_import(module: str, purpose: str, *, is_required: bool) -> dict[str, Any]:
    found = importlib.util.find_spec(module) is not None
    return {
        "name": module,
        "ok": found,
        "detail": purpose if found else f"missing: {purpose}",
        "required": is_required,
    }


def _check_binary(name: str, purpose: str, *, is_required: bool) -> dict[str, Any]:
    path = find_ast_grep() if name == "ast-grep" else shutil.which(name)
    return {
        "name": name,
        "ok": bool(path),
        "detail": path or f"missing: {purpose}",
        "required": is_required,
    }


def command_index(arguments: argparse.Namespace) -> Reply:
    """Write skills-index.html and skills-index.json."""
    workspace = open_workspace(arguments)
    html_path, json_path, document = write_index(
        workspace, workspace.read_settings(), date.today().isoformat()
    )
    numbers = document["numbers"]
    lines = [
        f"Wrote {html_path} and {json_path}",
        f"{numbers['skills']} skill(s), {numbers['fields']} field(s), "
        f"{numbers['dependencies']} dependencies",
    ]
    return Reply(
        {
            "html": str(html_path),
            "json": str(json_path),
            "skills": numbers["skills"],
            "fields": numbers["fields"],
        },
        lines,
    )


def command_check(arguments: argparse.Namespace) -> Reply:
    """List skills made stale by code changes; regenerate them with --regenerate."""
    workspace = open_workspace(arguments)
    settings = workspace.read_settings()
    generated = generated_paths(workspace)
    changed = [
        path
        for path in list_changed_files(workspace.root, arguments.since)
        if not any(path == item or path.startswith(f"{item}/") for item in generated)
    ]
    graph = None if arguments.no_graph else _refreshed_graph(workspace)
    report = find_drift(workspace, graph, changed)
    regenerated: list[str] = []
    if arguments.regenerate and report.stale_skills:
        graphify_graph = try_load_graphify_graph(workspace, graph) if graph is not None else None
        analyzer = make_analyzer(settings.analyzer, workspace, arguments.replay_dir)
        table = workspace.read_routes()
        for skill in report.stale_skills:
            entry = table.find(skill)
            if entry is not None:
                outcome = generate_route(
                    workspace,
                    settings,
                    entry,
                    GenerateOptions(
                        analyzer=analyzer,
                        graph=graph,
                        graphify_graph=graphify_graph,
                        should_load_graphify=False,
                    ),
                )
                if outcome.status == "written":
                    regenerated.append(skill)
    lines = [
        f"{len(report.changed_files)} changed file(s) since {arguments.since}",
        *(f"stale: {skill}" for skill in report.stale_skills),
        *(f"no saved slice (regenerate to be safe): {skill}" for skill in report.unknown_skills),
        *(f"regenerated: {skill}" for skill in regenerated),
    ]
    if not report.stale_skills:
        lines.append("Every skill is current.")
    data = {
        "since": arguments.since,
        "changed_files": list(report.changed_files),
        "stale": list(report.stale_skills),
        "unknown": list(report.unknown_skills),
        "regenerated": regenerated,
    }
    return Reply(data, lines, is_ok=not report.stale_skills or bool(arguments.regenerate))


def _refreshed_graph(workspace: Workspace) -> Any:
    try:
        return load_graph(workspace, should_refresh=True)
    except SkillgenError as error:
        logger.warning("continuing without a code graph: %s", error)
        return None


def try_load_graphify_graph(workspace: Workspace, graph: CodeGraph | None) -> GraphifyGraph | None:
    """Load the rich Graphify graph once, or continue without it.

    Args:
        workspace: The workspace.
        graph: The collapsed code graph, which supplies staleness information.

    Returns:
        The query graph, or None when Graphify's CLI is unavailable or fails.
    """
    if graph is None:
        return None
    try:
        return load_graphify_graph(workspace, graph)
    except (GraphError, OSError) as error:
        logger.warning("continuing without Graphify's query graph: %s", error)
        return None


def command_export(arguments: argparse.Namespace) -> Reply:
    """Export skills (and the index page) as a folder, a zip, one skill or a plugin."""
    workspace = open_workspace(arguments)
    settings = workspace.read_settings()
    chosen = choose_prefix(settings, workspace.root, arguments.name or "")
    plugin = chosen if arguments.plugin else ""
    one_skill = chosen if arguments.one_skill else ""
    # Each layout gets its own destination: a plugin and a bundled skill share a name
    # but not their contents, and one must not overwrite the other.
    default = (
        workspace.root
        / "dist"
        / ("skill" if one_skill else ".")
        / (plugin or one_skill or "skills")
    )
    target = Path(arguments.out or default).resolve()
    result = export_skills(
        workspace,
        workspace.skills_folder(settings),
        target,
        as_zip=arguments.zip,
        plugin_name=plugin,
        app_name=settings.app_name,
        one_skill_name=one_skill,
    )
    lines = [
        f"Exported {len(result.skills)} skill(s) to {result.path}",
        "MANIFEST.sha256 lists a hash of every file.",
        *describe_export_use(one_skill, plugin, len(result.skills)),
    ]
    return Reply(
        {
            "path": str(result.path),
            "skills": list(result.skills),
            "files": result.files,
            "plugin": plugin,
            "skill": one_skill,
        },
        lines,
    )


def describe_export_use(one_skill: str, plugin: str, pages: int) -> list[str]:
    """Say where this export can be used, and warn when an upload would refuse it.

    An upload that takes one skill at a time (Claude's or ChatGPT's skill settings)
    refuses an archive holding more than one `SKILL.md`, which is what a plain export
    of several pages is.

    Args:
        one_skill: The bundled skill's name, when the pages were bundled.
        plugin: The plugin name, when the export is a plugin.
        pages: How many page skills were exported.

    Returns:
        Lines to print.
    """
    if one_skill:
        return [f"One skill named {one_skill}: upload it where an AI takes one skill at a time."]
    if plugin:
        return ["A plugin: install it in Claude Code, or share it from the plugin directory."]
    if pages > 1:
        return [
            f"One folder per page, to copy into a skills folder. An upload that takes one "
            f"skill at a time refuses this ({pages} skills in one archive): use "
            f"`{TOOL_NAME} export --one-skill --zip` for that.",
        ]
    return []


def command_export_chatgpt(arguments: argparse.Namespace) -> Reply:
    """Export skills as one skills-only ChatGPT plugin, as a folder or a zip."""
    workspace = open_workspace(arguments)
    settings = workspace.read_settings()
    plugin = choose_prefix(settings, workspace.root, arguments.name or "")
    target = Path(arguments.out or (workspace.root / "dist" / "chatgpt" / plugin)).resolve()
    result = export_chatgpt_plugin(
        workspace,
        workspace.skills_folder(settings),
        target,
        as_zip=arguments.zip,
        plugin_name=plugin,
        app_name=settings.app_name,
    )
    use = (
        "Upload the zip at https://platform.openai.com/plugins (Skills only)."
        if arguments.zip
        else "Add the folder to a ChatGPT desktop marketplace, or rerun with --zip to upload it."
    )
    lines = [
        f"Exported {len(result.skills)} skill(s) as the ChatGPT plugin {plugin} to {result.path}",
        "MANIFEST.sha256 lists a hash of every file.",
        use,
    ]
    return Reply(
        {
            "path": str(result.path),
            "skills": list(result.skills),
            "files": result.files,
            "plugin": plugin,
        },
        lines,
    )


def command_probe(arguments: argparse.Namespace) -> Reply:
    """Probe one route on a running dev or staging copy and save what it saw."""
    from skillgen.probe.runner import probe_route, probe_route_at  # noqa: PLC0415 - optional extra

    workspace = open_workspace(arguments)
    settings = workspace.read_settings()
    if not settings.app_url and not arguments.url:
        raise ConfigError(f"set a dev URL first: {TOOL_NAME} init --url http://localhost:3000")
    entry = _named_entry(workspace, settings, arguments.route, None, try_load_graph(workspace))
    probed = (
        probe_route_at(workspace, settings, entry, arguments.url)
        if arguments.url
        else probe_route(workspace, settings, entry)
    )
    capture = workspace.page_folder(entry.skill) / "probe" / "probe.json"
    proven = sum(1 for f in probed.fields if f.is_proven)
    lines = [
        f"Probed {probed.url}: {len(probed.fields)} field(s), {proven} proven, "
        f"{len(probed.conditions)} condition(s), {len(probed.dependencies)} dependenc(ies)",
        f"Saved {capture}. Nothing was submitted.",
    ]
    return Reply(
        {
            "route": entry.route,
            "skill": entry.skill,
            "url": probed.url,
            "fields": len(probed.fields),
            "proven": proven,
            "conditions": len(probed.conditions),
            "dependencies": len(probed.dependencies),
            "capture": str(capture),
        },
        lines,
    )


def command_login(arguments: argparse.Namespace) -> Reply:
    """Log in once in a browser window; the session is saved for probing."""
    from skillgen.probe.runner import STORAGE_STATE, save_login  # noqa: PLC0415 - optional extra

    workspace = open_workspace(arguments)
    url = arguments.url or workspace.read_settings().app_url
    if not url:
        raise ConfigError(f"give a URL: {TOOL_NAME} login --url http://localhost:3000/login")
    path = workspace.secrets_folder / STORAGE_STATE
    save_login(url, path)
    return Reply(
        {"url": url, "storage_state": str(path)},
        [f"Saved the session to {path}. It is gitignored and never exported."],
    )


def _add_setup_parsers(commands: Any) -> None:
    init = commands.add_parser("init", help=f"create .{TOOL_NAME}/ and its config")
    init.add_argument("--app-name", help="the app's display name")
    init.add_argument("--url", help="base URL of a running dev or staging copy")
    init.add_argument("--environment", choices=[env.value for env in Environment])
    init.add_argument("--name", help="prefix for every skill name")
    init.add_argument("--analyzer", choices=[kind.value for kind in AnalyzerKind])
    routes = commands.add_parser("routes", help="find routes and write routes.json")
    routes.add_argument("--all", action="store_true", help="every route (the default)")
    routes.add_argument("--route", action="append", help="add a route by hand (repeatable)")
    routes.add_argument(
        "--include", action="append", help="route glob to keep, such as 'developer/*'"
    )
    routes.add_argument("--exclude", action="append", help="route glob to drop")
    routes.add_argument("--name", help="prefix for every skill name")
    routes.add_argument("--no-graph", action="store_true", help="do not build the code graph")
    routes.add_argument(
        "--ask-claude",
        action="store_true",
        help="also let Claude Code list routes from the code graph's likely router files",
    )
    routes.add_argument(
        "--no-claude",
        action="store_true",
        help="never call Claude Code, even when no route is found",
    )
    prepare = commands.add_parser(
        "prepare", help="write the slice and prompt for Claude Code to analyse a route"
    )
    prepare.add_argument("--route", required=True)
    prepare.add_argument("--name", help="the skill name for this route")
    prepare.add_argument("--no-graph", action="store_true")


def command_logs(arguments: argparse.Namespace) -> Reply:
    """Show the run logs of this workspace: the latest one, or a list."""
    workspace = open_workspace(arguments)
    logs = list_logs(workspace.folder)
    if not logs:
        return Reply(
            {"logs": [], "latest": "", "tail": []}, ["No logs yet; run any command first."]
        )
    latest = logs[0]
    tail = latest.read_text(encoding="utf-8").splitlines()[-arguments.lines :]
    lines = (
        [f"{path.name}" for path in logs[: arguments.count]]
        if arguments.list
        else [f"Latest log: {latest}", *tail]
    )
    return Reply(
        {
            "logs": [str(path) for path in logs[: arguments.count]],
            "latest": str(latest),
            "tail": tail,
        },
        lines,
    )


def _add_upkeep_parsers(commands: Any) -> None:
    commands.add_parser("index", help="write skills-index.html and skills-index.json")
    check = commands.add_parser("check", help="list skills made stale by code changes")
    check.add_argument(
        "--since", default="HEAD~1", help="git reference to compare with (default HEAD~1)"
    )
    check.add_argument("--regenerate", action="store_true", help="regenerate stale skills")
    check.add_argument("--replay-dir", help="recorded analyses, when the analyzer is replay")
    check.add_argument(
        "--no-graph", action="store_true", help="match changed files against slices only"
    )
    export = commands.add_parser(
        "export", help="export skills as a folder, zip or Claude Code plugin"
    )
    export.add_argument("--zip", action="store_true", help="write one zip file")
    export.add_argument("--plugin", action="store_true", help="lay out as a Claude Code plugin")
    export.add_argument(
        "--one-skill",
        action="store_true",
        help="bundle every page into one skill (one SKILL.md), for an upload that takes "
        "one skill at a time",
    )
    export.add_argument("--name", help="plugin or skill name (default: the app's prefix)")
    export.add_argument("--out", help="destination folder (default dist/<name>)")
    chatgpt = commands.add_parser(
        "export-chatgpt", help="export skills as one ChatGPT plugin (skills only)"
    )
    chatgpt.add_argument("--zip", action="store_true", help="write one zip file, ready to upload")
    chatgpt.add_argument("--name", help="plugin name (default: the app's prefix)")
    chatgpt.add_argument("--out", help="destination folder (default dist/chatgpt/<name>)")
    probe = commands.add_parser(
        "probe", help="probe one route on a running dev copy (needs the probe extra)"
    )
    probe.add_argument("--route", required=True)
    probe.add_argument("--url", help="concrete page URL, for routes with parameters")
    login = commands.add_parser("login", help="log in once in a browser window for probing")
    login.add_argument("--url", help="login page (default: the app URL)")
    logs = commands.add_parser("logs", help="show the latest run log (every command writes one)")
    logs.add_argument("--list", action="store_true", help="list recent logs instead")
    logs.add_argument("--lines", type=int, default=60, help="lines of the latest log to show")
    logs.add_argument("--count", type=int, default=10, help="logs to list")


def _add_generate_parser(commands: Any) -> None:
    generate = commands.add_parser("generate", help="generate one skill per route")
    target = generate.add_mutually_exclusive_group(required=True)
    target.add_argument("--route", help="one route (or its skill name)")
    target.add_argument("--all", action="store_true", help="every route in routes.json")
    generate.add_argument(
        "--name", help="with --route: the skill name; with --all: the prefix for every skill"
    )
    generate.add_argument("--url", help="base URL of a running dev or staging copy; implies --xy")
    generate.add_argument(
        "--xy",
        action="store_true",
        help="also measure where each field sits on the dev copy (x/y); never removes fields",
    )
    generate.add_argument(
        "--open",
        action="append",
        metavar="STEP",
        help="with --route: what to click before the form shows (a CSS selector or "
        "text:Label); repeat for several clicks; saved to routes.json",
    )
    generate.add_argument(
        "--code-only", action="store_true", help="never open a browser (the default)"
    )
    generate.add_argument("--analyzer", choices=[kind.value for kind in AnalyzerKind])
    generate.add_argument("--replay-dir", help="recorded analyses for --analyzer replay")
    generate.add_argument("--concurrency", type=int, help="routes analysed at once")
    generate.add_argument(
        "--description", help="use this skill description instead of the generated one"
    )
    generate.add_argument(
        "--include", action="append", help="route glob to keep, such as 'developer/*'"
    )
    generate.add_argument("--exclude", action="append", help="route glob to drop")
    generate.add_argument(
        "--force", action="store_true", help="also retry routes marked as having no form"
    )
    generate.add_argument(
        "--overwrite",
        action="store_true",
        help="recreate skills that already exist; without it they are left as they are",
    )
    generate.add_argument(
        "--no-graph", action="store_true", help="skip the code graph; slice entry files only"
    )


def _add_url_parser(commands: Any) -> None:
    """Add URL generation; Any is the shared argparse subcommand adapter."""
    command = commands.add_parser("generate-url", help="generate from a URL without source code")
    command.add_argument("url", help="absolute HTTP(S) URL to read")
    command.add_argument("--name", required=True, help="exact skill name")
    command.add_argument("--description", help="use this skill description")
    command.add_argument("--overwrite", action="store_true", help="recreate an existing skill")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME, description="Compile an app's code into one Agent Skill per page."
    )
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json", action="store_true", help="print JSON (validated against its schema)"
    )
    common.add_argument("--root", help="repository root (default: the current folder or a parent)")
    common.add_argument("-v", "--verbose", action="count", default=0, help="more log output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    class _Commands:
        """Adds every subcommand with the shared --json, --root and -v options."""

        @staticmethod
        def add_parser(name: str, **options: Any) -> argparse.ArgumentParser:
            return subparsers.add_parser(name, parents=[common], **options)

    commands = _Commands()
    _add_setup_parsers(commands)
    _add_generate_parser(commands)
    _add_url_parser(commands)
    questions = commands.add_parser("questions", help="list questions for the developer")
    questions.add_argument("--skill")
    questions.add_argument("--all", action="store_true", help="include answered questions")
    answer = commands.add_parser("answer", help="answer a question")
    answer.add_argument("id")
    answer.add_argument("answer")
    add_rule = commands.add_parser(
        "add-rule", help="add a rule to a skill (or every skill with --global)"
    )
    add_rule.add_argument("skill", nargs="?")
    add_rule.add_argument("rule")
    add_rule.add_argument("--check", help="machine check, such as 'legal_name ^A' or 'age min 18'")
    add_rule.add_argument("--global", dest="is_global", action="store_true")
    validate = commands.add_parser("validate", help="check skill folders and scan them for secrets")
    validate.add_argument("skills", nargs="*")
    install = commands.add_parser("install", help=f"add /{TOOL_NAME} to Claude Code")
    install.add_argument(
        "--target", help="Claude folder (default ~/.claude; use ./.claude for one project)"
    )
    install.add_argument(
        "--no-chromium",
        action="store_true",
        help="skip downloading Chromium, which --xy needs",
    )
    doctor = commands.add_parser("doctor", help="check installed tools")
    doctor.add_argument("--fix", action="store_true", help="download Chromium for the probe")
    _add_upkeep_parsers(commands)
    return parser


HANDLERS: dict[str, Callable[[argparse.Namespace], Reply]] = {
    "init": command_init,
    "routes": command_routes,
    "prepare": command_prepare,
    "generate": command_generate,
    "generate-url": command_generate_url,
    "questions": command_questions,
    "answer": command_answer,
    "add-rule": command_add_rule,
    "validate": command_validate,
    "install": command_install,
    "doctor": command_doctor,
    "index": command_index,
    "check": command_check,
    "export": command_export,
    "export-chatgpt": command_export_chatgpt,
    "probe": command_probe,
    "login": command_login,
    "logs": command_logs,
}


def emit(command: str, reply: Reply, *, as_json: bool) -> None:
    """Print a reply as text or as schema-checked JSON.

    Args:
        command: The command name.
        reply: The reply.
        as_json: Print JSON instead of text.
    """
    if not as_json:
        for line in reply.lines:
            print(line)
        return
    payload = {"ok": reply.is_ok, "command": command, **reply.data}
    problems = find_schema_problems(payload, f"cli/{command}")
    if problems:
        # A schema mismatch is a bug in skillgen; say so instead of printing bad JSON.
        payload = {
            "ok": False,
            "command": command,
            "error": "internal: output does not match its schema: " + problems[0],
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def use_utf8_output() -> None:
    """Write standard output and error as UTF-8 even when they are piped.

    Piped output on Windows defaults to the ANSI code page, which cannot encode marks
    such as the check mark and crashed `doctor --fix | Select-Object`.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line.

    Args:
        argv: Arguments without the program name; defaults to `sys.argv[1:]`.

    Returns:
        The exit code.
    """
    use_utf8_output()
    arguments = build_parser().parse_args(argv)
    arguments.command_line = list(argv if argv is not None else sys.argv[1:])
    log_path = start_logging(
        arguments.verbose, _log_folder(arguments), arguments.command, arguments.command_line
    )
    started = time.monotonic()
    try:
        try:
            reply = HANDLERS[arguments.command](arguments)
        except SkillgenError as error:
            logger.error("%s failed: %s", arguments.command, error)
            _report_error(arguments, str(error), log_path)
            return EXIT_ERROR
        except Exception:
            # Unexpected errors are bugs: keep the traceback in the log, then re-raise.
            logger.exception("%s crashed", arguments.command)
            if log_path:
                print(f"Full log: {log_path}", file=sys.stderr)
            raise
        logger.info(
            "%s finished in %.1fs (ok=%s)",
            arguments.command,
            time.monotonic() - started,
            reply.is_ok,
        )
        emit(arguments.command, reply, as_json=arguments.json)
        if log_path and not reply.is_ok and not arguments.json:
            print(f"Full log: {log_path}", file=sys.stderr)
        if reply.needs_action:
            return EXIT_NEEDS
        return EXIT_OK if reply.is_ok else EXIT_FAILED
    finally:
        stop_logging()


def _log_folder(arguments: argparse.Namespace) -> Path | None:
    """The workspace folder that receives this run's log, if there is one."""
    start = Path(arguments.root or ".").resolve()
    root = find_workspace_root(start)
    if root is None and arguments.command == "init":
        root = start
    return root / WORKSPACE_DIR if root is not None else None


def _report_error(arguments: argparse.Namespace, message: str, log_path: Path | None) -> None:
    if arguments.json:
        payload = {"ok": False, "command": arguments.command, "error": message}
        print(json.dumps(payload, ensure_ascii=False))
        return
    print(f"error: {message}", file=sys.stderr)
    if log_path:
        print(f"Full log: {log_path}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
