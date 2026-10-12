"""A small fill script `SKILL.md` carries in full, instead of pointing at fill.js.

Pointing at `scripts/fill.js` costs a reader twice: once reading the file and once
passing its text to the browser's JavaScript tool. Carrying a compact setter in
`SKILL.md` makes that one cost instead of two, and leaves the full engine on disk for
the fields the setter reports it cannot do.

When the probe measured the page, the setter also checks the live page against that
measurement before it writes anything. The check is an optimisation and a safety net,
never a requirement: a skill without a layout fills as before, and a check that fails
leaves the page untouched so Claude can inspect it normally. Stored positions are only
ever compared, never clicked; anything clicked is measured on the screen at hand.
"""

from __future__ import annotations

import json

from skillgen import TOOL_NAME
from skillgen.model.page import MANUAL_STRATEGIES, Box, FieldSpec, PageModel, Strategy, View

# One letter per strategy, so a field map of forty fields stays a few hundred bytes.
STRATEGY_CODES = {
    Strategy.NATIVE_INPUT: "i",
    Strategy.NATIVE_SELECT: "s",
    Strategy.CHOICE: "c",
    Strategy.ARIA_COMBOBOX: "b",
    Strategy.ARIA_TREE: "t",
    Strategy.ARIA_LISTBOX: "l",
    Strategy.RICH_TEXT: "r",
    Strategy.FILE: "f",
    Strategy.STEPS: "x",
}

# Statuses the setter returns per key, documented in the generated SKILL.md.
STATUSES = ("ok", "partial", "rejected", "missing", "escalate", "unknown")

# What the layout check can report, documented in the generated SKILL.md.
LAYOUT_STATES = ("match", "resized", "blocked", "changed")

# How long to wait for a combobox's own debounced search before reading its list.
COMBOBOX_WAIT_MS = 900

# The path separator an aria-tree value uses between levels.
PATH_SEPARATOR = " / "

# Below this share of landmarks agreeing, the page is treated as changed and nothing is
# written. 0.85 lets one of eight landmarks wobble without tripping, but not two.
LAYOUT_MIN_SCORE = 0.85

# Viewport widths within this many CSS pixels count as the same screen. Layout follows
# width (breakpoints, columns); height only decides what is scrolled into view.
VIEWPORT_SLACK_PX = 8

# A fingerprint of fewer than three landmarks proves too little to act on; more than
# eight adds bytes without adding much certainty.
MIN_LANDMARKS = 3
MAX_LANDMARKS = 8

_OPEN = """await (async function (S, M, G, V, O) {
  var store = window[__STORE__] = window[__STORE__] || {};
"""

_MEASURE = """  var index = {}, n;
  for (n = 0; n < M.length; n++) { index[M[n][0]] = M[n][1]; }
  function find(key) {
    try { return index[key] ? document.querySelector(index[key]) : null; }
    catch (error) { return null; }
  }
  function rectOf(el) { var r = el.getBoundingClientRect(); return r.width || r.height ? r : null; }
"""

# `put` writes through the prototype's setter: frameworks that control an input wrap the
# element's own setter, and a write through that wrapper makes them ignore the event that
# follows, so the page shows a value the app never took. Boxes are clicked, not set, for
# the same reason: such frameworks listen for the click.
_HELPERS = """  function ev(el, name) { el.dispatchEvent(new Event(name, { bubbles: true })); }
  function put(el, prop, value) {
    var own = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), prop);
    if (own && own.set) { own.set.call(el, value); } else { el[prop] = value; }
  }
  function sleep(ms) { return new Promise(function (go) { setTimeout(go, ms); }); }
  function clickable(node, want) {
    var kids = node.querySelectorAll('*'), i, kid;
    for (i = 0; i < kids.length; i++) {
      kid = kids[i];
      if (kid.children.length === 0 && (kid.textContent || '').trim() === want) { return kid; }
    }
    return node;
  }
  function byText(root, want) {
    var nodes = root.querySelectorAll('[role=option],[role=treeitem],li,option'), i, node;
    for (i = 0; i < nodes.length; i++) {
      node = nodes[i];
      if ((node.textContent || '').trim().indexOf(want) !== 0) { continue; }
      if (node.tagName === 'OPTION') { put(root, 'value', node.value); ev(root, 'change'); }
      else { clickable(node, want).click(); }
      return true;
    }
    return false;
  }
  function manyByText(root, value) {
    var wants = [].concat(value), done = 0, i;
    for (i = 0; i < wants.length; i++) { if (byText(root, String(wants[i]).trim())) { done++; } }
    return done === wants.length ? 'ok' : (done ? 'partial' : 'rejected');
  }
  async function byPath(root, value) {
    var parts = String(value).split(__SEP__), i;
    for (i = 0; i < parts.length; i++) {
      if (!byText(root, parts[i].trim())) { return 'rejected'; }
      await sleep(60);
    }
    return 'ok';
  }
  function setChoice(selector, value) {
    var nodes = document.querySelectorAll(selector), wants = [].concat(value), done = 0, i, label;
    for (i = 0; i < nodes.length; i++) {
      label = ((nodes[i].parentNode || nodes[i]).textContent || '').trim();
      if (wants.indexOf(label) < 0 && wants.indexOf(nodes[i].value) < 0) { continue; }
      if (!nodes[i].checked) { nodes[i].click(); }
      if (nodes[i].checked) { done++; }
    }
    return done === wants.length ? 'ok' : (done ? 'partial' : 'rejected');
  }
  async function byCombobox(el, value) {
    el.focus(); put(el, 'value', String(value)); ev(el, 'input');
    await sleep(__WAIT__);
    var id = el.getAttribute('aria-controls') || el.getAttribute('aria-owns');
    var list = id ? document.getElementById(id) : null;
    if (!list) { return 'escalate'; }
    return byText(list, String(value)) ? 'ok' : 'rejected';
  }
  async function one(selector, code, value) {
    if (code === 'f' || code === 'x') { return 'escalate'; }
    if (code === 'c') { return setChoice(selector, value); }
    var el = document.querySelector(selector);
    if (!el) { return 'missing'; }
    if (code === 'r') { el.textContent = String(value); ev(el, 'input'); return 'ok'; }
    if (code === 't') { return byPath(el, value); }
    if (code === 'l') { return manyByText(el, value); }
    if (code === 'b') { return byCombobox(el, value); }
    if (code === 's') {
      put(el, 'value', String(value)); ev(el, 'change');
      if (String(el.value) === String(value)) { return 'ok'; }
      return byText(el, String(value)) ? 'ok' : 'rejected';
    }
    var kind = el.type || '';
    if (kind === 'checkbox' || kind === 'radio') {
      if (el.checked !== !!value) { el.click(); }
      return el.checked === !!value ? 'ok' : 'rejected';
    }
    put(el, 'value', String(value)); ev(el, 'input'); ev(el, 'change');
    return String(el.value) === String(value) ? 'ok' : 'rejected';
  }
"""

_VERIFY = """  function verify() {
    var vw = window.innerWidth, vh = window.innerHeight, same = Math.abs(vw - G.w) <= __SLACK__;
    var out = { state: 'changed', score: 0, viewport: [vw, vh], built: [G.w, G.h] };
    var anchor = find(G.a), base = anchor && rectOf(anchor);
    if (!base) { out.failed = [G.a + ':missing']; return out; }
    var failed = [], covered = [], seen = 0, floor = -Infinity, i, row, el, r, left, top, x, y, hit;
    for (i = 0; i < G.b.length; i++) {
      row = G.b[i]; el = find(row[0]); r = el && rectOf(el);
      if (!r) { failed.push(row[0] + (el ? ':hidden' : ':missing')); continue; }
      left = r.left - base.left; top = r.top - base.top;
      if (top < floor - Math.max(24, row[4] / 2)) { failed.push(row[0] + ':order'); continue; }
      floor = Math.max(floor, top);
      if (same && (Math.abs(left - row[1]) > Math.max(16, vw * 0.03)
          || Math.abs(top - row[2]) > Math.max(24, Math.abs(row[2]) * 0.06)
          || Math.abs(r.height - row[4]) > Math.max(10, row[4] * 0.3))) {
        failed.push(row[0] + ':moved'); continue;
      }
      x = r.left + r.width / 2; y = r.top + r.height / 2;
      if (x < 0 || y < 0 || x >= vw || y >= vh) { continue; }
      seen++; hit = document.elementFromPoint(x, y);
      if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) { covered.push(row[0]); }
    }
    out.score = Math.round(100 * (G.b.length - failed.length) / G.b.length) / 100;
    if (failed.length) { out.failed = failed; }
    if (covered.length) { out.covered = covered; }
    if (covered.length * 2 > seen && covered.length) { out.state = 'blocked'; }
    else if (out.score >= __MIN_SCORE__) { out.state = same ? 'match' : 'resized'; }
    return out;
  }
"""

_LOCATE = """  function locate(key) {
    var el = find(key), r;
    if (!el) { return 'missing'; }
    el.scrollIntoView({ block: 'center', inline: 'nearest' });
    r = rectOf(el);
    return r ? [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)] : 'hidden';
  }
"""

# Finds what one open step names: a CSS selector, or `text:Label` for a button, link or
# tab whose text, aria-label or title is exactly that label. The probe runs the same code,
# so the page it measures is the page the skill opens.
_STEP_TARGET = """  function stepTarget(step) {
    var want, nodes, i, node;
    if (step.indexOf('text:') !== 0) {
      try { return document.querySelector(step); } catch (error) { return null; }
    }
    want = step.slice(5).trim();
    nodes = document.querySelectorAll('button,a,summary,[role=button],[role=tab]');
    for (i = 0; i < nodes.length; i++) {
      node = nodes[i];
      if ((node.textContent || '').trim() === want || node.getAttribute('aria-label') === want
          || node.getAttribute('title') === want) { return node; }
    }
    return null;
  }
"""

# Clicks the open steps only while the form is hidden: an open step is often a toggle,
# and clicking it on an open form would close it.
_OPEN_FORM = """  async function openForm() {
    var first = find(__FIRST__), steps = __OPEN__, i, target;
    if (first && rectOf(first)) { return; }
    for (i = 0; i < steps.length; i++) {
      target = stepTarget(steps[i]);
      if (target) { target.click(); await sleep(500); }
    }
  }
"""

# Walks the views (steps, tabs, dialogs) in order: reaches each by its clicks only when
# a value belongs to it or later, checks its fields appeared, fills it, then leaves it.
# It never clicks submit; when the page will not move on, it stops and reports why. A
# view none of whose selectors the page can parse cannot be checked, so its clicks are
# trusted rather than stopping the walk there.
_VIEWS = """  var W = __VIEWS__, at = {}, w, q;
  for (w = 0; w < W.length; w++) { for (q = 0; q < W[w][3].length; q++) { at[W[w][3][q]] = w; } }
  function shows(w) {
    return W[w][3].some(function (k) { var el = find(k); return !!el && !!rectOf(el); });
  }
  function current() { var w = W.length; while (w-- && !shows(w)) {} return w; }
  async function press(steps) {
    for (var i = 0, el; i < steps.length; i++) {
      if (!(el = stepTarget(steps[i]))) { return steps[i] + ':missing'; }
      el.click(); await sleep(300);
    }
    return '';
  }
  function checkable(w) {
    return W[w][3].some(function (k) {
      try { document.querySelector(index[k]); return true; } catch (error) { return false; }
    });
  }
  async function reach(w) {
    var why = await press(W[w][1]), t = 0;
    while (!why && checkable(w) && !shows(w) && t++ < 20) { await sleep(150); }
    return why || (shows(w) || !checkable(w) ? '' : 'not shown');
  }
  function pageErrors() {
    return [].slice.call(document.querySelectorAll(__ERRORS__)).filter(rectOf).map(function (el) {
      return (el.textContent || el.getAttribute('aria-label') || el.name || '').trim().slice(0, 80);
    }).filter(String).slice(0, 5);
  }
  function partOf(k) { return k in at ? at[k] : -1; }
  function wanted(values, from, goal) {
    if (from <= goal) { return true; }
    for (var k in values) { if (index[k] && partOf(k) >= from) { return true; } }
    return false;
  }
  async function walk(values, report, view) {
    var R = {}, start = current(), goal = -1, w, k, why;
    for (w = 0; w < W.length; w++) { if (W[w][0] === view) { goal = w; } }
    for (k in values) {
      if (!index[k] || partOf(k) < start) { R[k] = index[k] ? 'escalate' : 'unknown'; }
    }
    for (w = start; w < W.length; w++) {
      if (w > start) {
        if (!wanted(values, w, goal)) { break; }
        if ((why = await reach(w))) {
          report.stopped = { view: W[w][0], reason: why, errors: pageErrors() };
          for (k in values) { if (!(k in R)) { R[k] = 'escalate'; } }
          break;
        }
      }
      Object.assign(R, await fill(values, w));
      if (w >= 0 && w !== goal && W[w][2].length) { await press(W[w][2]); }
    }
    if ((w = current()) >= 0) { report.view = W[w][0]; }
    report.fill = R;
  }
"""

_FILL_PART = """  async function fill(values, part) {
    var R = {}, i, row, k;
    for (i = 0; i < M.length; i++) {
      row = M[i]; k = row[0];
      if (!(k in values) || partOf(k) !== part) { continue; }
      if (row[3]) { await sleep(__WAIT__); }
      try { R[k] = await one(row[1], row[2], values[k]); } catch (error) { R[k] = 'escalate'; }
    }
    return R;
  }
"""

# Each field is tried on its own, so a selector the page cannot parse stops only that field.
_FILL = """  async function fill(values) {
    var R = {}, known = {}, i, row, k;
    for (i = 0; i < M.length; i++) {
      row = M[i]; k = row[0]; known[k] = 1;
      if (!(k in values)) { continue; }
      if (row[3]) { await sleep(__WAIT__); }
      try { R[k] = await one(row[1], row[2], values[k]); } catch (error) { R[k] = 'escalate'; }
    }
    for (k in values) { if (!known[k]) { R[k] = 'unknown'; } }
    return R;
  }
"""

_RUN_CHECKED = """  async function run(values, options) {
__OPEN_CALL__    var report = {};
    if (!(options && options.verify === false)__AT_START__) {
      report.layout = verify();
      if (report.layout.state === 'changed' || report.layout.state === 'blocked') {
        return JSON.stringify(report);
      }
    }
__FILL_CALL__    return JSON.stringify(report);
  }
"""

_RUN_PLAIN = """  async function run(values) {
__OPEN_CALL__    return JSON.stringify({ fill: await fill(values || {}) });
  }
"""

_RUN_WALK = """  async function run(values, options) {
__OPEN_CALL__    var report = {};
__FILL_CALL__    return JSON.stringify(report);
  }
"""

_FILL_ALL_CALL = "    report.fill = await fill(values || {});\n"
_WALK_CALL = "    await walk(values || {}, report, options && options.view);\n"

_CLOSE = """  store[S] = { __API__ };
  return run(V, O);
})"""


def store_name() -> str:
    """Return the `window` property the setter keeps itself under between calls.

    Returns:
        The property name, derived from the tool name.
    """
    return f"__{TOOL_NAME}"


def field_selector(page: PageModel, key: str) -> str:
    """Return the selector the setter uses for a field, rows resolved to the first row.

    A field inside a repeat group carries a selector relative to one row, so it is
    prefixed with the group's row selector. `querySelector` then resolves it to the
    first row, which is all the setter handles; further rows escalate.

    Args:
        page: The page model.
        key: The field key.

    Returns:
        A CSS selector, or an empty string when the field is unknown.
    """
    spec = next((item for item in page.fields if item.key == key), None)
    if spec is None:
        return ""
    if not spec.group:
        return spec.selector
    group = next((item for item in page.groups if item.id == spec.group), None)
    if group is None or not group.row_selector:
        return spec.selector
    return f"{group.row_selector} {spec.selector}"


def ordered_fields(page: PageModel) -> list[FieldSpec]:
    """Return the fields in the order the setter should work through them.

    The page model already holds its fields in fill order, which is not cosmetic: a
    field that reveals others, or whose options another field depends on, has to be
    set first. This wrapper names that dependency so it is not lost in a refactor.

    Args:
        page: The page model.

    Returns:
        The fields, in fill order.
    """
    return list(page.fields)


def build_field_map(page: PageModel) -> list[list[object]]:
    """Build the ordered field table the setter takes.

    Args:
        page: The page model.

    Returns:
        One `[key, selector, strategy code]` row per field, in fill order, with a
        fourth element set when the field's options load asynchronously and the setter
        must wait for the field it depends on.
    """
    rows: list[list[object]] = []
    for spec in ordered_fields(page):
        row: list[object] = [
            spec.key,
            field_selector(page, spec.key),
            STRATEGY_CODES[spec.strategy],
        ]
        if spec.options_from is not None and spec.options_from.is_async:
            row.append(1)
        rows.append(row)
    return rows


def is_landmark_candidate(spec: FieldSpec) -> bool:
    """Whether a field is steady enough on load to fingerprint the page with.

    Fields that appear on a condition, repeat in rows, or need a person's hand are left
    out: their presence on load says little about whether the page is the same one.

    Args:
        spec: The field.

    Returns:
        True when the field can serve as a landmark.
    """
    return not spec.group and spec.visible_if is None and spec.strategy not in MANUAL_STRATEGIES


def choose_landmarks(page: PageModel) -> list[tuple[str, Box]]:
    """Choose the fields whose positions fingerprint the page.

    One field per row is kept, so the order still holds when two columns collapse
    into one on a narrower screen. The rows are then thinned evenly, always keeping the
    first and the last.

    Args:
        page: The page model.

    Returns:
        `(key, box)` pairs from top to bottom, or an empty list when too few fields
        were measured to prove anything.
    """
    if page.layout is None:
        return []
    candidates = [
        (spec.key, box)
        for spec in page.fields
        if is_landmark_candidate(spec)
        and page.view_of(spec.key) is None
        and (box := page.layout.box_of(spec.key)) is not None
    ]
    candidates.sort(key=lambda item: (item[1].top, item[1].left))
    rows: list[tuple[str, Box]] = []
    for key, box in candidates:
        if rows and box.top < rows[-1][1].top + rows[-1][1].height:
            continue
        rows.append((key, box))
    if len(rows) < MIN_LANDMARKS:
        return []
    if len(rows) <= MAX_LANDMARKS:
        return rows
    step = (len(rows) - 1) / (MAX_LANDMARKS - 1)
    return [rows[index] for index in sorted({round(i * step) for i in range(MAX_LANDMARKS)})]


def build_geometry(page: PageModel) -> dict[str, object] | None:
    """Build the layout fingerprint the setter checks the live page against.

    Offsets are taken from the first landmark rather than from the page, so content
    above the form, centring on a wider screen and the scroll position all cancel out.

    Args:
        page: The page model.

    Returns:
        `{w, h, a, b}`: the viewport it was measured at, the anchor key, and each
        landmark as `[key, left, top, width, height]` relative to the anchor; or None
        when the page has no usable layout.
    """
    landmarks = choose_landmarks(page)
    if not landmarks or page.layout is None:
        return None
    anchor_key, anchor = landmarks[0]
    return {
        "w": page.layout.viewport_width,
        "h": page.layout.viewport_height,
        "a": anchor_key,
        "b": [
            [key, box.left - anchor.left, box.top - anchor.top, box.width, box.height]
            for key, box in landmarks
        ],
    }


def render_engine(
    has_checks: bool = False,
    has_manual: bool = False,
    open_steps: tuple[str, ...] = (),
    first_key: str = "",
    *,
    views: tuple[View, ...] = (),
    error_selector: str = "",
) -> str:
    """Return the setter's JavaScript, holding only the parts the page needs.

    Every part costs a reader on every fill, so the layout check is included only
    with a layout to check against, `locate` only when some field is done by hand, the
    opener only when the form starts closed, and the view walker only when some fields
    sit in steps, tabs or dialogs.

    Args:
        has_checks: Include the layout check.
        has_manual: Include `locate`, for fields Claude must click itself.
        open_steps: What to click before the form is on screen.
        first_key: A field whose visibility shows the form is open.
        views: Parts of the form shown only after clicks, in fill order.
        error_selector: What marks a field error on the page, to report why a view
            would not open.

    Returns:
        The engine source, ready to be followed by its five arguments.
    """
    has_open, has_views = bool(open_steps), bool(views)
    needs_find = has_checks or has_manual or has_open or has_views
    parts = [_OPEN, _MEASURE if needs_find else "", _HELPERS]
    parts += [_VERIFY if has_checks else "", _LOCATE if has_manual else ""]
    parts += [_STEP_TARGET if has_open or has_views else "", _OPEN_FORM if has_open else ""]
    parts += [_VIEWS + _FILL_PART if has_views else _FILL]
    plain = _RUN_WALK if has_views else _RUN_PLAIN
    parts += [_RUN_CHECKED if has_checks else plain, _CLOSE]
    constants = {
        "__AT_START__": " && current() < 0" if has_views else "",
        "__FILL_CALL__": _WALK_CALL if has_views else _FILL_ALL_CALL,
        "__VIEWS__": json.dumps(
            [[v.name, list(v.enter), list(v.leave), list(v.keys)] for v in views]
        ),
        "__ERRORS__": json.dumps(", ".join(filter(None, ["[role=alert]", error_selector]))),
        "__OPEN_CALL__": "    await openForm();\n" if has_open else "",
        "__OPEN__": json.dumps(list(open_steps)),
        "__FIRST__": json.dumps(first_key),
        "__STORE__": json.dumps(store_name()),
        "__SEP__": json.dumps(PATH_SEPARATOR),
        "__WAIT__": str(COMBOBOX_WAIT_MS),
        "__SLACK__": str(VIEWPORT_SLACK_PX),
        "__MIN_SCORE__": str(LAYOUT_MIN_SCORE),
        "__API__": "run: run, locate: locate" if has_manual else "run: run",
    }
    source = "".join(parts)
    for placeholder, value in constants.items():
        source = source.replace(placeholder, value)
    return source


def find_steady_key(page: PageModel) -> str:
    """Return a field that is on screen whenever the form is, to tell whether it is open.

    Args:
        page: The page model.

    Returns:
        The first field that is neither conditional, repeated nor done by hand; failing
        that the first field; or an empty string for a page without fields.
    """
    steady = next(
        (
            spec.key
            for spec in page.fields
            if is_landmark_candidate(spec) and page.view_of(spec.key) is None
        ),
        "",
    )
    return steady or (page.fields[0].key if page.fields else "")


def build_open_script() -> str:
    """Build the probe's script that clicks a route's open steps, like the skill does.

    Returns:
        A JavaScript function taking the steps and returning `clicked` or `missing` for
        each, for the probe to run before it measures the page.
    """
    return (
        "async function (steps) {\n"
        + _STEP_TARGET
        + "  var done = [], i, target;\n"
        + "  for (i = 0; i < steps.length; i++) {\n"
        + "    target = stepTarget(steps[i]);\n"
        + "    if (!target) { done.push('missing'); continue; }\n"
        + "    target.click(); done.push('clicked');\n"
        + "    await new Promise(function (go) { setTimeout(go, 500); });\n"
        + "  }\n"
        + "  return done;\n"
        + "}"
    )


def has_manual_fields(page: PageModel) -> bool:
    """Whether any field must be done by hand, so `locate` earns its bytes.

    Args:
        page: The page model.

    Returns:
        True when a field's strategy needs Claude's own browser actions.
    """
    return any(spec.strategy in MANUAL_STRATEGIES for spec in page.fields)


def flatten_values(page: PageModel, values: dict[str, object]) -> dict[str, object]:
    """Flatten repeat-group values onto the flat keys the field map uses.

    Callers describe rows the way the page reads them, `{"references": [{"name": ...}]}`.
    The setter has one selector per field and resolves it to the first row, so the first
    row's values move onto `references[].name` style keys and further rows are dropped.

    Args:
        page: The page model.
        values: Values as a caller writes them.

    Returns:
        Values keyed the way the field map is keyed.
    """
    group_ids = {group.id for group in page.groups}
    flat: dict[str, object] = {}
    for key, value in values.items():
        if key not in group_ids:
            flat[key] = value
            continue
        rows = value if isinstance(value, list) else [value]
        first = rows[0] if rows else {}
        if isinstance(first, dict):
            for name, item in first.items():
                flat[f"{key}[].{name}"] = item
    return flat


def _compact(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def build_inline_setter(
    page: PageModel, values: dict[str, object], options: dict[str, object] | None = None
) -> str:
    """Build the complete call `SKILL.md` shows.

    Args:
        page: The page model.
        values: Example values, with repeat-group rows still nested.
        options: The call's options, such as `{"view": "Step 3"}`; none by default.

    Returns:
        One JavaScript expression taking the skill name, field map, layout fingerprint
        (or null), values and options, ready for the browser's JavaScript tool.
    """
    geometry = build_geometry(page)
    arguments = [
        _compact(page.skill),
        _compact(build_field_map(page)),
        _compact(geometry),
        _compact(flatten_values(page, values)),
        _compact(options or {}),
    ]
    engine = render_engine(
        geometry is not None,
        has_manual_fields(page),
        page.open_steps,
        find_steady_key(page),
        views=page.views,
        error_selector=page.submit.field_error if page.submit else "",
    )
    return f"{engine}(\n" + ",\n".join(arguments) + "\n)"


def build_probe_call(page: PageModel, values: dict[str, object], view: str) -> str:
    """Build the call the probe runs to reach one view, filling the parts before it.

    It is the skill's own setter, so the probe reaches each view exactly the way the
    skill will, and a step that checks its fields before moving on gets valid values.

    Args:
        page: The page model.
        values: Example values for the fields before the view.
        view: The view's name.

    Returns:
        A JavaScript expression (a promise of the setter's JSON report).
    """
    call = build_inline_setter(page, values, {"verify": False, "view": view})
    return call.removeprefix("await ")


def build_rerun_call(page: PageModel, should_skip_check: bool = False) -> str:
    """Build the short call that reuses the setter already loaded in the page.

    Args:
        page: The page model.
        should_skip_check: Fill without checking the layout first, for when Claude has
            already inspected the page itself.

    Returns:
        A JavaScript expression with `{...}` where the values go.
    """
    target = f"window[{_compact(store_name())}][{_compact(page.skill)}]"
    options = ', {"verify": false}' if should_skip_check else ""
    return f"await {target}.run({{...}}{options})"


def build_locate_call(page: PageModel, key: str) -> str:
    """Build the call that scrolls a field into view and returns its on-screen centre.

    Args:
        page: The page model.
        key: The field key.

    Returns:
        A JavaScript expression.
    """
    return f"window[{_compact(store_name())}][{_compact(page.skill)}].locate({_compact(key)})"
