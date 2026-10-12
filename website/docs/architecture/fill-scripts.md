---
title: Fill scripts
description: The inline setter and fill.js - ES2019, no dependencies, prototype setters, per-key statuses, views and the optional layout check.
---

# Fill scripts

A skill fills its page with JavaScript that runs inside the page. There are two scripts, and
both follow the same rules:

- **Plain ES2019, no dependencies.** No `?.`, `??`, `||=`, numeric separators, `globalThis`,
  `replaceAll`, `.at()`, `Promise.allSettled`, or classes with private fields.
  `generate.fill_script.find_forbidden_syntax` checks it, and CI runs `node --check` on the
  bench skill's `fill.js`.
- **Compact JSON only.** Page text in results is truncated and treated as data.

## The inline setter (fast path)

`generate/inline_setter.py` builds a small setter that the skill carries in full in
`references/fill.md`, with the page's selector map, so one `javascript_tool` call fills the
page and nothing else is read first. Measured on the bench skill, this took one fill from
10,869 to 3,877 tokens compared with pointing at `fill.js`.

It reports one status per key: `ok`, `partial`, `rejected`, `missing`, `escalate`, `unknown`.

Each part of the setter costs a reader on every fill, so `render_engine` includes only what
the page needs:

| Part | Included when |
| --- | --- |
| Views walk (`_VIEWS`) | The page has views (steps, tabs, dialogs) |
| Open steps (`_OPEN_FORM`, `_STEP_TARGET`) | The form is behind a click |
| Layout check (`_VERIFY`) | The page has a measured layout |
| `locate(key)` | Some field must be done by hand |

### Writing values the way a framework sees them

Both scripts write values through the element prototype's own setter (`put` in the setter,
`setValue` in `fill.js`) and click checkboxes rather than setting `checked`. A
framework-controlled input ignores a direct `el.value = …`, while a naive read-back still says
`ok`. `test_setter_fills_inputs_a_framework_controls` (a browser test) rebuilds that trap and
fails on a direct write.

### Open steps

An open step is a CSS selector or `text:Label`. One piece of JavaScript resolves them,
`_STEP_TARGET`: the probe runs it through `build_open_script`, and the skill runs it in
`openForm`, which clicks only while the form's first steady field is hidden, because an open
step is often a toggle.

### Views

`_VIEWS` reaches each part with `stepTarget`, waits for its fields, fills it, leaves it, and
reports `view` and `stopped` (with the page's `[role=alert]` and field error texts).
`run(values, {"view": name})` stops in a part. The probe reaches each view with the same call
(`build_probe_call`), filling earlier parts with example values.

### The layout check

The check is optional and exists only with a probe-measured layout. The probe measures each
control's box from its final selector at a 1280×900 viewport. `choose_landmarks` picks 3 to 8
landmark fields, one per row, from fields that are in no view and always shown;
`build_geometry` writes them relative to the first. At fill time the setter reports
`layout.state`:

| State | Meaning | Writes? |
| --- | --- | --- |
| `match` | Same layout | Yes |
| `resized` | Same structure at another viewport | Yes |
| `blocked` | Something covers the form | No |
| `changed` | Not the expected layout | No |

A failed check writes nothing, but it must never stop the AI inspecting the page and filling
with `{"verify": false}`. Stored positions only ever verify; anything clicked is measured live
with `locate(key)`.

## `fill.js` (fallback)

`scripts/fill.js` is `generate/fill_engine.js` plus a generated field map at the top. The
engine is the same in every skill (`ENGINE_VERSION = 1`); only the map differs. The AI reads it
only when the setter answers `escalate` for some keys.

- Size is measured in **bytes**: `MAX_SCRIPT_BYTES = 48000`. The field map is written one
  entry per line. A size rule is never met by making lines longer.
- It walks the fields in fill order, waits until each exists and is visible (which handles
  conditional fields), applies the field's strategy, waits for dependent options to load,
  checks compiled rules locally, reads each value back, and collects errors from
  `aria-invalid`, `role=alert` and the text next to each field.
- It refuses to run when `location.hostname` differs from the skill's `app-url` hostname.
- `validate.spec.check_fill_script` checks its size and that the engine is untouched and
  ES2019.

## Testing the scripts

`uv run pytest -m browser` starts the bench server and runs the scripts in Chromium for every
bench case: fill, follow-up, server rejection, wrong host, missing field. It checks what the
server received, and that the probe created zero records. See [Testing](../contributing/testing.md).
