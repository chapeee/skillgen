---
title: Field positions with --xy
description: Measure where each field sits on a running dev copy, ship it as references/layout.json, and let the skill check the live page first.
---

# Field positions with `--xy`

`generate` has two modes, and the command chooses:

| Command | What you get |
| --- | --- |
| `skillgendev generate --route /x --name my-skill` | **Normal.** Everything from the code. No browser, no x/y. Works on every page |
| `skillgendev generate --route /x --name my-skill --xy` | **Everything normal gives, plus x/y.** Opens the page on your dev copy in Chromium and measures where each field sits |

`--xy` only adds. It never removes a field, changes what the skill says about one, or
adds a question. If it cannot measure the page, you still get the normal skill, and the AI
running skillgendev is told why.

## Requirements

- The `probe` extra (`uv tool install --editable ".[probe]"`) and Chromium
  (`skillgendev doctor --fix`).
- A **dev or staging** copy. Never production: the probe refuses an environment marked
  `production`, intercepts and cancels write requests, and never submits anything.

Set the address once, or pass it per run:

```bash
skillgendev init --url http://localhost:3000
skillgendev generate --route /campaigns/new --name new-campaign --xy
skillgendev generate --route /campaigns/new --name new-campaign --url http://localhost:3000   # implies --xy
```

If you forget the address, the run writes the skill from the code and the agent asks you
for it, then runs the command again.

## What the run measures

The skill is always built from the code first. `--xy` then opens the code-built page,
makes any [open steps](./hidden-forms.md#open-when-the-form-is-hidden-behind-a-button),
and measures every field **by the skill's own selector**. That means a measured box always
belongs to the element the skill will fill, and the measuring function can only return a
layout, never change a field.

The run reports how many fields got x/y (for example `x/y for 16 fields`). When x/y cannot
be measured, x/y from an earlier run is kept for every field whose selector has not
changed. It only ever verifies, so an outdated box can never aim a click.

## What ships with the skill

Every measured position ships in `references/layout.json`: the window size, each field's
x/y, width and height, and its offset from the first field, plus which view it was measured
in. The AI reads it only when it has to check the page by hand, and measures a field on
screen again before clicking it. `export` copies it with the skill.

## The layout check at fill time

With a layout, the fill call first checks the live page against up to eight landmark
fields (one per row), compared by structure rather than pixels, so a different screen size
is fine:

- `match` or `resized`: the form is filled.
- `blocked` (a dialog covers the form) or `changed` (not the layout expected): nothing is
  written; the AI takes a screenshot and inspects the page as usual.

The check is a shortcut, never a gate, and adds roughly 1,250 tokens to each fill.

## Signing in

If the page needs a sign-in, you do not have to know that beforehand. The skill is written
from the code anyway, and the agent asks whether to open a browser window so you can sign
in:

```bash
skillgendev login --url http://localhost:3000/login
```

You sign in and close the window. The session is saved in
`.skillgendev/secrets/storage-state.json` (gitignored, never exported), and the next `--xy` run
uses it.

## Looking at one page: `probe`

```bash
skillgendev probe --route /campaigns/new
skillgendev probe --route /campaigns/:id/edit --url http://localhost:3000/campaigns/7/edit
```

`probe` opens one route on the dev copy and shows what the browser finds there: which
fields, which values it can set, what a submit would send (keys and types, never values).
It saves the capture to `.skillgendev/pages/<skill>/probe/` and does not change a skill. Use it
to see what the probe sees.

## What can stop `--xy`

| Need | What the agent does |
| --- | --- |
| `url` | Writes the skill from the code, then asks you for the address |
| `server` | Writes the skill from the code, then asks you to start your dev server |
| `chromium` | Writes the skill from the code, then asks whether to download Chromium (about 150 MB) |
| `probe` | The probe extra is not installed; asks you to reinstall with it |
| `login` | Writes the skill from the code, then asks whether to open a sign-in window |
| `open` | No field showed. First tries the clicks the code points to; asks which button opens the form only if none works |

Each of these is a [`next` step](../concepts/agent-handoff.md). Nothing is analysed twice
while the page's code is unchanged.
