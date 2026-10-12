"""Probe one route on a running dev or staging copy (spec section 5, step 2).

The probe reads every control, submits the empty form to collect client-side errors,
changes each select, radio group and checkbox to find conditional fields and dependent
option lists, fills every field with synthetic values through the real fill engine to
prove each strategy, and intercepts the submit request so nothing is ever saved.

Playwright is imported lazily, so the core works without the `probe` extra.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import socket
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from skillgen import TOOL_NAME
from skillgen.assets import read_fill_engine
from skillgen.config import Environment, Settings
from skillgen.errors import (
    ActionNeededError,
    Need,
    ProbeError,
    ProbeUnavailableError,
    UnsafeEnvironmentError,
)
from skillgen.generate.examples import build_example_values
from skillgen.generate.fill_script import build_fill_script
from skillgen.generate.inline_setter import build_open_script, build_probe_call
from skillgen.model.facts import Provenance, Source
from skillgen.model.page import (
    Box,
    FieldSpec,
    Layout,
    Operator,
    PageModel,
    Strategy,
    SubmitSpec,
    ValueType,
)
from skillgen.model.probe import ProbedCondition, ProbedDependency, ProbedField, ProbedPage
from skillgen.model.route import RouteEntry
from skillgen.model.serialize import box_from_list, box_to_list, viewport_from_list
from skillgen.probe.capture import probed_page_to_dict
from skillgen.probe.classify import build_probed_fields, describe_shape
from skillgen.routes.naming import find_route_params
from skillgen.workspace import Workspace, write_json

logger = logging.getLogger(__name__)

CHROMIUM_VARIABLE = f"{TOOL_NAME.upper()}_CHROMIUM"
STORAGE_STATE = "storage-state.json"
MAX_OPTIONS_TRIED = 6
SETTLE_MS = 500
# The screen size layouts are measured at. Skills check the live viewport against it
# and fall back to structural checks on any other size, so this is a reference point,
# not a requirement.
CAPTURE_VIEWPORT = {"width": 1280, "height": 900}
_PROBE_PROVENANCE = Provenance(sources=(Source.RUNTIME_PROBED,), confidence=0.9)


def load_extract_script() -> str:
    """Read the in-page extraction function shipped with the probe."""
    return resources.files("skillgen.probe").joinpath("extract.js").read_text("utf-8")


@dataclass
class RequestLog:
    """Requests seen while probing.

    Attributes:
        reads: Number of GET requests so far.
        blocked: Bodies of write requests that were intercepted and cancelled.
    """

    reads: int = 0
    blocked: list[str] = field(default_factory=list)


def _require_playwright() -> Any:
    try:
        from playwright import sync_api  # noqa: PLC0415 - optional extra
    except ImportError as error:
        raise ProbeUnavailableError(
            f"the probe needs Playwright: reinstall {TOOL_NAME} with the probe extra (see README)"
        ) from error
    return sync_api


def launch_chromium(playwright: Any, *, is_headless: bool = True) -> Any:
    """Launch Chromium, using `<TOOL>_CHROMIUM` when set.

    Args:
        playwright: The started Playwright object.
        is_headless: Run without a window.

    Returns:
        The browser.

    Raises:
        ActionNeededError: If Chromium has not been downloaded yet.
        ProbeError: If it does not start for another reason.
    """
    executable = os.environ.get(CHROMIUM_VARIABLE)
    options: dict[str, Any] = {"headless": is_headless}
    if executable:
        options["executable_path"] = executable
    try:
        return playwright.chromium.launch(**options)
    except _require_playwright().Error as error:
        if "doesn't exist" in str(error) or "playwright install" in str(error):
            raise ActionNeededError(Need.CHROMIUM, "", "Chromium is not downloaded yet") from error
        raise ProbeError(f"Chromium did not start: {str(error)[:200]}") from error


@contextmanager
def open_page(storage_state: Path | None) -> Iterator[tuple[Any, RequestLog]]:
    """Open a page whose write requests are intercepted and cancelled.

    Args:
        storage_state: Saved login state, if any.

    Yields:
        (page, request log).
    """
    sync_api = _require_playwright()
    log = RequestLog()

    def guard(route: Any) -> None:
        request = route.request
        if request.method in ("GET", "HEAD", "OPTIONS"):
            log.reads += 1
            route.continue_()
            return
        # Never let the probe create or change data.
        log.blocked.append(request.post_data or "")
        route.abort()

    with sync_api.sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        state = str(storage_state) if storage_state and storage_state.exists() else None
        context = browser.new_context(storage_state=state, viewport=CAPTURE_VIEWPORT)
        page = context.new_page()
        page.route("**/*", guard)
        try:
            yield page, log
        finally:
            context.close()
            browser.close()


def read_controls(page: Any) -> dict[str, Any]:
    """Run the extraction script in the page.

    Args:
        page: The Playwright page.

    Returns:
        `{title, controls, submit}` as the page reported them.
    """
    result: dict[str, Any] = page.evaluate(load_extract_script())
    return result


def to_field_specs(fields: list[ProbedField]) -> list[FieldSpec]:
    """Turn probed fields into field specs so the fill engine can drive them.

    Args:
        fields: Probed fields.

    Returns:
        Field specs with probe provenance.
    """
    return [
        FieldSpec(
            key=f.key,
            label=f.label,
            value_type=f.value_type,
            strategy=f.strategy,
            selector=f.selector,
            provenance=_PROBE_PROVENANCE,
            options=f.options,
            limits=f.limits,
        )
        for f in fields
        if not f.is_repeated
    ]


def build_probe_script(fields: list[ProbedField], submit_selector: str) -> str:
    """Build a fill.js for probing (no host check, every probed field).

    Args:
        fields: Probed fields.
        submit_selector: The submit control.

    Returns:
        The script.
    """
    page = PageModel(
        route="/",
        skill="probe",
        title="probe",
        app_name="",
        app_url="",
        fields=tuple(to_field_specs(fields)),
        submit=SubmitSpec(selector=submit_selector),
    )
    return build_fill_script(page, read_fill_engine())


def run_fill(page: Any, script: str, values: dict[str, Any]) -> dict[str, Any]:
    """Run the fill engine in the page.

    Args:
        page: The Playwright page.
        script: The probe's fill script.
        values: Values by key.

    Returns:
        The engine's result.
    """
    result: dict[str, Any] = json.loads(page.evaluate(script + f"\n__fill({json.dumps(values)})"))
    return result


def settle(page: Any) -> None:
    """Wait for the page to react to a change."""
    page.wait_for_timeout(SETTLE_MS)
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:  # noqa: BLE001 - a busy page is fine; the next read decides
        logger.debug("page did not go idle")


def snapshot(page: Any) -> dict[str, tuple[bool, tuple[str, ...]]]:
    """Read field visibility and options without retaining any field values.

    Args:
        page: The page whose current state should be read.

    Returns:
        A field key to `(visible, options)` mapping.
    """
    fields = build_probed_fields(read_controls(page)["controls"])
    return {field.key: (field.is_visible, field.options) for field in fields}


def _controllers(fields: list[ProbedField]) -> list[tuple[ProbedField, list[Any]]]:
    """Return safe enum and boolean controls whose values may reveal behaviour."""
    controllers: list[tuple[ProbedField, list[Any]]] = []
    for probed in fields:
        if not probed.is_visible or probed.is_repeated:
            continue
        if (
            probed.strategy in (Strategy.CHOICE, Strategy.NATIVE_SELECT)
            and probed.value_type is ValueType.ENUM
        ):
            controllers.append((probed, list(probed.options[:MAX_OPTIONS_TRIED])))
        elif probed.value_type is ValueType.BOOLEAN:
            controllers.append((probed, [True]))
    return controllers


def find_behaviour(
    page: Any,
    url: str,
    fields: list[ProbedField],
    script: str,
    log: RequestLog,
    *,
    open_steps: tuple[str, ...] = (),
) -> tuple[list[ProbedCondition], list[ProbedDependency]]:
    """Find conditional fields and dependent option lists with bounded interactions.

    Each controller is reloaded once so values tried for one control cannot contaminate
    the baseline for another. This detailed walk is used by the explicit `probe`
    command; generation's `--xy` path measures the code-built page without this walk.

    Args:
        page: The page to interact with.
        url: The page URL, reloaded between controllers.
        fields: Controls found on the opening page.
        script: The fill engine for those controls.
        log: The request log, used to identify async option changes.
        open_steps: Clicks needed before the form is visible.

    Returns:
        Conditional-field and dependent-option findings.
    """
    started = time.monotonic()
    conditions: list[ProbedCondition] = []
    dependencies: dict[tuple[str, str], ProbedDependency] = {}
    for controller, values in _controllers(fields):
        load_page(page, url, open_steps)
        baseline = snapshot(page)
        for value in values:
            appeared, changed = observe_controller(
                page, script, controller, value, baseline=baseline, log=log
            )
            if appeared:
                conditions.append(ProbedCondition(controller.key, str(value), appeared))
            for target, is_async in changed.items():
                dependencies[(controller.key, target)] = ProbedDependency(
                    controller.key, target, is_async
                )
    found_dependencies = list(dependencies.values())
    logger.info(
        "probe behaviour finished in %.2fs: %d condition(s), %d dependenc(ies)",
        time.monotonic() - started,
        len(conditions),
        len(found_dependencies),
    )
    return conditions, found_dependencies


def observe_controller(
    page: Any,
    script: str,
    controller: ProbedField,
    value: Any,
    *,
    baseline: dict[str, tuple[bool, tuple[str, ...]]],
    log: RequestLog,
) -> tuple[tuple[str, ...], dict[str, bool]]:
    """Apply one controller value and compare it with that controller's baseline."""
    reads_before = log.reads
    run_fill(page, script, {controller.key: value})
    settle(page)
    current = snapshot(page)
    appeared = tuple(
        key
        for key, (visible, _) in current.items()
        if visible and not baseline.get(key, (False, ()))[0]
    )
    changed = {
        key: log.reads > reads_before
        for key, (_, options) in current.items()
        if key != controller.key and options and options != baseline.get(key, (False, ()))[1]
    }
    return appeared, changed


def open_form(page: Any, open_steps: tuple[str, ...]) -> None:
    """Make a route's open clicks, so the form is on screen; warn about any not found.

    Args:
        page: The Playwright page, already loaded.
        open_steps: What to click, in order; nothing happens when empty.
    """
    if not open_steps:
        return
    clicked = page.evaluate(build_open_script(), list(open_steps))
    missing = [step for step, done in zip(open_steps, clicked, strict=False) if done != "clicked"]
    if missing:
        logger.warning("open step not found on %s: %s", page.url, ", ".join(missing))
    settle(page)


def load_page(
    page: Any,
    url: str,
    open_steps: tuple[str, ...] = (),
) -> None:
    """Load a page, let it settle, and open its form.

    Args:
        page: The Playwright page.
        url: The page URL.
        open_steps: What to click before the form is on screen.

    Raises:
        ActionNeededError: If nothing answers at the URL.
        ProbeError: If the page fails to load for another reason.
    """
    started = time.monotonic()
    try:
        page.goto(url)
    except _require_playwright().Error as error:
        message = str(error).splitlines()[0][:200]
        if "net::ERR_" in message:
            raise ActionNeededError(
                Need.SERVER, url, f"nothing answers at {url} ({message})"
            ) from error
        raise ProbeError(f"could not open {url}: {message}") from error
    settle(page)
    open_form(page, open_steps)
    logger.debug("probe loaded %s in %.2fs", url, time.monotonic() - started)


def empty_submit_errors(page: Any, script: str) -> tuple[bool, dict[str, str]]:
    """Submit the untouched form (intercepted) and read each field's error.

    Args:
        page: The Playwright page.
        script: The probe's fill script.

    Returns:
        (whether the submit ran, error message by field key).
    """
    page.evaluate(script)
    result = json.loads(page.evaluate("__submit()"))
    if result.get("error"):
        return False, {}
    errors = result.get("errors", {}) or {}
    return True, {str(key): str(message) for key, message in errors.items() if key != "_page"}


def choose_values(
    fields: list[ProbedField],
    reveal: Mapping[str, Any] | None = None,
    conditions: list[ProbedCondition] | None = None,
) -> dict[str, Any]:
    """Pick a synthetic value for every field visible on load.

    A field that appears on another's value is filled by the second pass of
    `prove_strategies`, which re-reads the page after this one.

    Args:
        fields: Fields seen on load.
        reveal: Values the code says bring conditional fields on screen.
        conditions: Runtime findings used when code did not provide a reveal value.

    Returns:
        Values by key for the fields visible on load.
    """
    specs = to_field_specs(fields)
    page = PageModel(
        route="/", skill="probe", title="probe", app_name="", app_url="", fields=tuple(specs)
    )
    values = build_example_values(page)
    for controller in {condition.controller for condition in conditions or ()}:
        candidates = [
            condition for condition in conditions or () if condition.controller == controller
        ]
        best = max(candidates, key=lambda condition: len(condition.appeared))
        values[controller] = True if best.value == "True" else best.value
    values.update(reveal or {})
    visible = {f.key for f in fields if f.is_visible}
    return {key: value for key, value in values.items() if key in visible}


def reveal_values(page: PageModel | None) -> dict[str, Any]:
    """Values that bring a page's conditional fields on screen, from the code's own rules.

    A field that appears on another's value can only be filled, and so proven, once it
    is on screen. The code already states what brings it there, so that is read rather
    than searched for by setting every control in turn and watching.

    Args:
        page: The model built from the code, or None on a first run.

    Returns:
        Controller key to the value that reveals something.
    """
    if page is None:
        return {}
    found: dict[str, Any] = {}
    for spec in page.fields:
        condition = spec.visible_if
        if condition is None:
            continue
        if condition.operator is Operator.CHECKED:
            found[condition.field] = True
        elif condition.operator is Operator.IN and condition.values:
            found[condition.field] = condition.values[0]
    return found


def prove_strategies(
    page: Any,
    url: str,
    fields: list[ProbedField],
    submit_selector: str,
    *,
    open_steps: tuple[str, ...] = (),
    reveal: Mapping[str, Any] | None = None,
    conditions: list[ProbedCondition] | None = None,
) -> tuple[set[str], list[ProbedField]]:
    """Fill every reachable field with synthetic values and keep what the page accepted.

    Args:
        page: The Playwright page.
        url: The page URL.
        fields: Fields seen on load.
        submit_selector: The submit control.
        open_steps: What to click before the form is on screen.
        reveal: Values the code says bring conditional fields on screen.
        conditions: Runtime conditions found before filling.

    Returns:
        (keys proven, every field seen during the fill, including revealed ones).
    """
    load_page(page, url, open_steps)
    script = build_probe_script(fields, submit_selector)
    proven = set(
        run_fill(page, script, choose_values(fields, reveal, conditions)).get("filled", [])
    )
    settle(page)
    revealed = build_probed_fields(read_controls(page)["controls"])
    second = {
        f.key: f.options[0]
        if f.value_type in (ValueType.ENUM, ValueType.MULTI_ENUM) and f.options
        else build_example_values(
            PageModel(
                route="/",
                skill="p",
                title="p",
                app_name="",
                app_url="",
                fields=tuple(to_field_specs([f])),
            )
        ).get(f.key)
        for f in revealed
        if f.is_visible and f.key not in proven and not f.is_repeated
    }
    script = build_probe_script(revealed, submit_selector)
    proven |= set(
        run_fill(page, script, {k: v for k, v in second.items() if v is not None}).get("filled", [])
    )
    return proven, revealed


def probe_url(
    url: str,
    storage_state: Path | None = None,
    open_steps: tuple[str, ...] = (),
    reveal: Mapping[str, Any] | None = None,
) -> ProbedPage:
    """Probe one page.

    Args:
        url: The page URL on a dev or staging host.
        storage_state: Saved login state, if the page needs a session.
        open_steps: What to click, after every load, before the form is on screen.
        reveal: Values the code says bring conditional fields on screen, so they can
            be filled and proven.

    Returns:
        What the probe saw.

    Raises:
        ProbeUnavailableError: If Playwright is not installed.
        ProbeError: If the page cannot be probed.
    """
    with open_page(storage_state) as (page, log):
        load_page(page, url, open_steps)
        first = read_controls(page)
        fields = build_probed_fields(first["controls"])
        if not fields:
            return ProbedPage(
                url=url,
                title=str(first["title"]),
                fields=(),
                clickables=tuple(first.get("clickables", ())),
            )
        submit = first.get("submit") or {}
        submit_selector = str(submit.get("selector", ""))
        script = build_probe_script(fields, submit_selector)
        has_empty_submit, errors = (
            empty_submit_errors(page, script) if submit_selector else (False, {})
        )
        conditions, dependencies = find_behaviour(
            page, url, fields, script, log, open_steps=open_steps
        )
        proven, revealed = prove_strategies(
            page,
            url,
            fields,
            submit_selector,
            open_steps=open_steps,
            reveal=reveal,
            conditions=conditions,
        )
        log.blocked.clear()
        if submit_selector:
            page.evaluate("__submit()")
        shape = describe_shape(log.blocked[-1]) if log.blocked else {}
    # Fields revealed by a later interaction were measured in a changed page, so only
    # boxes read on load describe the page a skill will open.
    every = {f.key: f for f in fields} | {
        f.key: replace(f, box=None) for f in revealed if f.key not in {g.key for g in fields}
    }
    final = tuple(
        replace(
            f,
            is_proven=f.key in proven,
            is_required=f.is_required or f.key in errors,
            error_message=errors.get(f.key, ""),
        )
        for f in every.values()
    )
    width, height = viewport_from_list(first.get("viewport"))
    return ProbedPage(
        url=url,
        title=str(first["title"]),
        fields=final,
        conditions=tuple(conditions),
        dependencies=tuple(dependencies),
        submit_selector=submit_selector,
        submit_label=str(submit.get("label", "")),
        body_shape=shape,
        has_empty_submit=has_empty_submit,
        viewport_width=width,
        viewport_height=height,
        clickables=tuple(first.get("clickables", ())),
    )


def find_open_steps(workspace: Workspace, entry: RouteEntry) -> tuple[str, ...]:
    """Return a route's open clicks: the developer's, else those the code analysis found.

    Args:
        workspace: The workspace.
        entry: The route.

    Returns:
        What to click before the form is on screen; empty when it shows on load.
    """
    if entry.open_steps:
        return entry.open_steps
    saved = workspace.read_page(entry.skill)
    return saved.open_steps if saved is not None else ()


def probe_route(workspace: Workspace, settings: Settings, entry: RouteEntry) -> ProbedPage:
    """Probe a route on the configured dev or staging copy and save the capture.

    Args:
        workspace: The workspace.
        settings: Project settings with `app_url`.
        entry: The route.

    Returns:
        What the probe saw.

    Raises:
        UnsafeEnvironmentError: If the environment is production.
        ProbeError: If the route has parameters or the page cannot be probed.
    """
    if settings.environment is Environment.PRODUCTION:
        raise UnsafeEnvironmentError(
            "the probe only runs on dev or staging; set environment in config.json"
        )
    if find_route_params(entry.route):
        raise ProbeError(
            f"{entry.route} has parameters; probe it once by URL with `{TOOL_NAME} probe --url …`"
        )
    probed = probe_url(
        settings.app_url.rstrip("/") + entry.route,
        workspace.secrets_folder / STORAGE_STATE,
        find_open_steps(workspace, entry),
        reveal_values(workspace.read_page(entry.skill)),
    )
    write_json(
        workspace.page_folder(entry.skill) / "probe" / "probe.json", probed_page_to_dict(probed)
    )
    return probed


def probe_route_at(
    workspace: Workspace, settings: Settings, entry: RouteEntry, url: str
) -> ProbedPage:
    """Probe a route at an explicit URL (for routes with parameters) and save it.

    Args:
        workspace: The workspace.
        settings: Project settings.
        entry: The route.
        url: The concrete page URL, such as `http://localhost:3000/projects/7/edit`.

    Returns:
        What the probe saw.

    Raises:
        UnsafeEnvironmentError: If the environment is production.
    """
    if settings.environment is Environment.PRODUCTION:
        raise UnsafeEnvironmentError(
            "the probe only runs on dev or staging; set environment in config.json"
        )
    probed = probe_url(
        url, workspace.secrets_folder / STORAGE_STATE, find_open_steps(workspace, entry)
    )
    write_json(
        workspace.page_folder(entry.skill) / "probe" / "probe.json", probed_page_to_dict(probed)
    )
    return probed


def load_measure_script() -> str:
    """Read the script that measures a skill's own selectors in the page."""
    return resources.files("skillgen.probe").joinpath("measure.js").read_text("utf-8")


@dataclass(frozen=True)
class Measurement:
    """Where a skill's selectors sat on a page, and whether it was a sign-in page.

    Attributes:
        width: The viewport width.
        height: The viewport height.
        boxes: A box for each selector that was on screen.
        is_sign_in: True when the page showed a password field or moved to another
            address instead of the one asked for.
    """

    width: int
    height: int
    boxes: dict[str, Box]
    is_sign_in: bool = False


@dataclass(frozen=True)
class Stage:
    """One look at the page while measuring: how to get there, and what to measure.

    Attributes:
        label: What is being looked at, for the log.
        call: The skill's own setter call that reaches it from a fresh load (filling
            the parts before it), or empty for the form as it opens.
        selectors: The selectors to measure there.
    """

    label: str
    call: str
    selectors: tuple[str, ...]


def measure_boxes(
    url: str,
    storage_state: Path | None,
    open_steps: tuple[str, ...],
    selectors: list[str],
    stages: tuple[Stage, ...] = (),
) -> Measurement:
    """Open a page, click its open steps, and measure the given selectors, then each stage.

    Every stage starts from a fresh load, so one that fails to reach its view cannot
    leave the next one on the wrong screen. A selector keeps the first box found.

    Args:
        url: The page URL on a dev or staging host.
        storage_state: Saved login state, if the page needs a session.
        open_steps: What to click before the form is on screen.
        selectors: The selectors to measure as the form opens.
        stages: Further views and revealed fields, each with how to reach it.

    Returns:
        The viewport and a box for each selector that was on screen.

    Raises:
        ProbeUnavailableError: If Playwright is not installed.
        ActionNeededError: If Chromium is missing or nothing answers at the URL.
    """
    with open_page(storage_state) as (page, _log):
        load_page(page, url, open_steps)
        found = page.evaluate(load_measure_script(), selectors)
        boxes = read_boxes(found)
        for stage in stages:
            for selector, box in measure_stage(page, url, open_steps, stage).items():
                boxes.setdefault(selector, box)
    width, height = viewport_from_list(found.get("viewport"))
    is_moved = str(found.get("path", "")).rstrip("/") != urlsplit(url).path.rstrip("/")
    return Measurement(width, height, boxes, bool(found.get("password")) or is_moved)


def read_boxes(found: dict[str, Any]) -> dict[str, Box]:
    """Read the boxes `measure.js` returned, leaving out what was not on screen.

    Args:
        found: The script's result.

    Returns:
        A box by selector.
    """
    boxes: dict[str, Box] = {}
    for selector, raw in found.get("boxes", []):
        box = box_from_list(raw)
        if box is not None:
            boxes[str(selector)] = box
    return boxes


def measure_stage(page: Any, url: str, open_steps: tuple[str, ...], stage: Stage) -> dict[str, Box]:
    """Reach one stage from a fresh load and measure its selectors.

    Args:
        page: The Playwright page.
        url: The page URL.
        open_steps: What to click before the form is on screen.
        stage: What to reach and measure.

    Returns:
        A box by selector, for those on screen.
    """
    load_page(page, url, open_steps)
    if stage.call:
        try:
            report = json.loads(page.evaluate(stage.call))
        except (_require_playwright().Error, ValueError) as error:
            logger.warning("could not reach %s: %s", stage.label, str(error)[:200])
            return {}
        if report.get("stopped"):
            logger.warning("could not reach %s: %s", stage.label, report["stopped"])
            return {}
        settle(page)
    boxes = read_boxes(page.evaluate(load_measure_script(), list(stage.selectors)))
    logger.info("%s: %d of %d field(s) on screen", stage.label, len(boxes), len(stage.selectors))
    return boxes


def find_xy_need(settings: Settings) -> tuple[Need, str] | None:
    """Find what stops `--xy` before any work is done, so a run never stops halfway.

    Args:
        settings: Settings for this run.

    Returns:
        What is missing and the URL it is about, or None when x/y can be measured (or
        was not asked for).
    """
    if not settings.should_probe:
        return None
    if not settings.app_url:
        return Need.URL, ""
    if importlib.util.find_spec("playwright") is None:
        return Need.PROBE, ""
    if not is_chromium_ready():
        return Need.CHROMIUM, ""
    if not is_answering(settings.app_url):
        return Need.SERVER, settings.app_url
    return None


def is_chromium_ready() -> bool:
    """Tell whether Playwright's Chromium (or `<TOOL>_CHROMIUM`) is on this computer."""
    executable = os.environ.get(CHROMIUM_VARIABLE)
    if executable:
        return Path(executable).is_file()
    sync_api = _require_playwright()
    with sync_api.sync_playwright() as playwright:
        return Path(playwright.chromium.executable_path).is_file()


def is_answering(url: str, timeout_seconds: float = 3.0) -> bool:
    """Tell whether anything listens at a URL's host and port.

    A plain connection is enough: any answer, even an error page or a certificate
    warning, means the dev server is up.

    Args:
        url: The app URL.
        timeout_seconds: How long to wait.

    Returns:
        True when the port accepts a connection.
    """
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        with socket.create_connection((parts.hostname or "localhost", port), timeout_seconds):
            return True
    except OSError:
        return False


def measure_page_layout(
    workspace: Workspace, settings: Settings, entry: RouteEntry, page_model: PageModel
) -> Layout | None:
    """Measure where a skill's fields sit on the dev copy, by the skill's own selectors.

    Measuring the skill's selectors, rather than matching what the probe finds to them,
    means every box belongs to the element the skill's layout check will read back.

    Args:
        workspace: The workspace.
        settings: Project settings with `app_url`.
        entry: The route, with any open steps.
        page_model: The page built from the code.

    Returns:
        The layout, or None when no field was on screen.

    Raises:
        UnsafeEnvironmentError: If the environment is production.
        ProbeError: If the route has parameters, so there is no single page to open.
        ActionNeededError: If the page asks the developer to sign in, nothing answers at
            the URL, or Chromium is missing.
    """
    if settings.environment is Environment.PRODUCTION:
        raise UnsafeEnvironmentError(
            "the probe only runs on dev or staging; set environment in config.json"
        )
    if find_route_params(entry.route):
        raise ProbeError(f"{entry.route} has parameters, so --xy has no single page to open")
    url = settings.app_url.rstrip("/") + entry.route
    keyed = [(spec.key, spec.selector) for spec in page_model.fields if not spec.group]
    steps = page_model.open_steps
    first = [
        spec.selector
        for spec in page_model.fields
        if not spec.group and is_on_open(page_model, spec)
    ]
    found = measure_boxes(
        url,
        workspace.secrets_folder / STORAGE_STATE,
        steps,
        first,
        plan_stages(page_model),
    )
    measured = tuple(
        (key, found.boxes[selector]) for key, selector in keyed if selector in found.boxes
    )
    write_json(
        workspace.page_folder(entry.skill) / "probe" / "layout.json",
        {
            "url": url,
            "open": list(steps),
            "viewport": [found.width, found.height],
            "boxes": {key: box_to_list(box) for key, box in measured},
        },
    )
    if not measured and keyed and found.is_sign_in:
        raise ActionNeededError(Need.LOGIN, url, f"{url} showed a sign-in page")
    if not measured and keyed:
        clicked = f" after clicking {', '.join(steps)}" if steps else ""
        raise ActionNeededError(Need.OPEN, url, f"no field was on screen at {url}{clicked}")
    if not measured or found.width <= 0:
        return None
    return Layout(viewport_width=found.width, viewport_height=found.height, boxes=measured)


def is_on_open(page: PageModel, spec: FieldSpec) -> bool:
    """Whether a field shows as soon as the form is open: in no view and unconditional."""
    return page.view_of(spec.key) is None and spec.visible_if is None


def plan_stages(page: PageModel) -> tuple[Stage, ...]:
    """Plan every further look at the page: each view, then each conditional field.

    A view is reached by the skill's own setter, filling the parts before it with
    example values so a step that checks its fields lets the probe through. A
    conditional field is revealed by setting the field it depends on.

    Args:
        page: The page model, with its views.

    Returns:
        The stages, in fill order.
    """
    examples = build_example_values(page)
    order = {spec.key: index for index, spec in enumerate(page.fields)}
    stages = [
        Stage(
            view.name,
            build_probe_call(page, values_before(page, examples, index), view.name),
            tuple(find_selectors(page, view.keys, conditional=False)),
        )
        for index, view in enumerate(page.views)
    ]
    for spec in sorted(page.fields, key=lambda item: order[item.key]):
        reveal = choose_reveal_value(page, spec, examples)
        if spec.group or spec.visible_if is None or reveal is None:
            continue
        view = page.view_of(spec.key)
        position = page.views.index(view) if view else -1
        values = values_before(page, examples, position) | {spec.visible_if.field: reveal}
        call = build_probe_call(page, values, view.name if view else "")
        stages.append(
            Stage(f"{spec.key} (when {spec.visible_if.field} is set)", call, (spec.selector,))
        )
    return tuple(stage for stage in stages if stage.selectors)


def values_before(page: PageModel, examples: dict[str, Any], position: int) -> dict[str, Any]:
    """Keep the example values of the fields on screen before a view.

    Args:
        page: The page model.
        examples: Example values by key (repeat-group rows nested under the group).
        position: The view's index; -1 for the form as it opens.

    Returns:
        The values for the form as it opens and every earlier view.
    """
    group_keys = {
        group.id: [spec.key for spec in page.fields if spec.group == group.id]
        for group in page.groups
    }
    kept: dict[str, Any] = {}
    for key, value in examples.items():
        keys = group_keys.get(key, [key])
        indexes = [page.views.index(view) if (view := page.view_of(k)) else -1 for k in keys]
        if indexes and max(indexes) < position:
            kept[key] = value
    return kept


def find_selectors(page: PageModel, keys: tuple[str, ...], *, conditional: bool) -> list[str]:
    """Return the selectors of a view's plain fields (or of its conditional ones)."""
    wanted = set(keys)
    return [
        spec.selector
        for spec in page.fields
        if spec.key in wanted and not spec.group and (spec.visible_if is not None) == conditional
    ]


def choose_reveal_value(page: PageModel, spec: FieldSpec, examples: dict[str, Any]) -> Any:
    """Pick a value for the field a conditional field depends on, so it shows.

    Args:
        page: The page model.
        spec: The conditional field.
        examples: Example values by key.

    Returns:
        A value that meets the condition, or None when none can be chosen safely.
    """
    condition = spec.visible_if
    if condition is None:
        return None
    controller = next((item for item in page.fields if item.key == condition.field), None)
    if controller is None:
        return None
    if condition.operator is Operator.CHECKED:
        return True
    if condition.operator is Operator.FILLED:
        return examples.get(controller.key)
    if condition.operator is Operator.IN:
        return condition.values[0] if condition.values else None
    others = [option for option in controller.options if option not in condition.values]
    return others[0] if others else None


def save_login(url: str, storage_state: Path) -> None:
    """Open a browser window, let the developer log in, then save the session.

    The session is written when the developer closes the window. It stays in the
    workspace's `secrets/` folder, which is never committed or exported.

    Args:
        url: The app's login or start page.
        storage_state: Where to save the session.
    """
    sync_api = _require_playwright()
    with sync_api.sync_playwright() as playwright:
        browser = launch_chromium(playwright, is_headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        page.wait_for_event("close", timeout=0)
        storage_state.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(storage_state))
        browser.close()
