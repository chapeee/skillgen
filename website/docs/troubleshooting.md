---
title: Troubleshooting
description: Fixes for the problems people meet most often with skillgendev - routes, Claude Code, x/y, exports and the docs site.
---

# Troubleshooting

Start with the log: `skillgendev logs` shows the latest run and its path, and every error prints
`Full log: <path>`. Per-route files in `.skillgendev/pages/<skill>/` show what Claude was asked and
answered. See [Logs and debugging](./guides/logs-and-debugging.md).

## Git Bash rewrites routes

**Symptom:** `skillgendev generate --route /campaigns/new` reports no such route, or mentions
`C:/Program Files/Git/campaigns/new`.

Git Bash rewrites anything that starts with `/` into a Windows path. skillgendev refuses such a
route rather than guessing. Use PowerShell, or in Git Bash:

```bash
MSYS_NO_PATHCONV=1 skillgendev generate --route /campaigns/new
skillgendev generate --route new-campaign        # or pass the skill's name instead
```

## A selector loses its quotes in PowerShell

`--open 'button[title="Audience settings"]'` can arrive without its inner quotes. Prefer
`--open "text:Audience settings"`, which works in every terminal.

## `skillgendev` is not found, or runs an old version

`skillgendev doctor` shows the folder `skillgendev` runs from. Reinstall from your clone with
`scripts/install-local.sh` or `.\scripts\install-local.ps1`; it removes old installs, clears uv's
cache and checks that `skillgendev` points at your clone.

## No routes were found

- Check that the app's folders are not under a skipped folder (`node_modules`, `dist`, hidden
  folders).
- Run `skillgendev routes --all --ask-claude` to let Claude Code read the code graph's likely router
  files.
- Add routes by hand: `skillgendev routes --route /leads/import`.
- For a stack you use often, [add a hint pack](./contributing/framework-support.md).

## A concrete route has no code files

With `--route /campaigns/42/edit`, skillgendev links the page to the pattern with the most
fixed segments. If two patterns fit equally well it links nothing and the analysis starts with no
files. Give the pattern route instead (`/campaigns/:id/edit`).

## Claude Code cannot run the analysis

If `claude` is not installed or not signed in, the run does not fail: the result has
`next.action: "analyse"` and exit code 3. Inside Claude Code, `/skillgendev` does the analysis
itself. In a terminal, run `claude` once to sign in, then run the same command again.

If the result says `need: "limit"`, Claude's own usage limit is reached. Wait until it resets
and run `then`; finished analyses are reused.

## `generate` says the skill exists

That is on purpose: an existing skill is never replaced by accident. Add `--overwrite`. Your
notes in the user section are kept, and the analysis is reused if the code is unchanged.

## A skill came out `invalid`

A check failed, so the old skill and its page data were kept. `problems` in the result (and
`skillgendev validate`) lists what failed: a name that breaks the Agent Skills rules, a description
too long, a body over 500 lines, a script too large, or a secret-scan finding.

## `--xy` measured no fields

The run still wrote the skill from the code, and its `next` says why:

| `need` | Fix |
| --- | --- |
| `url` | Give the dev address: `skillgendev init --url http://localhost:3000`, or `--url` |
| `server` | Start your dev server |
| `chromium` | `skillgendev doctor --fix` |
| `probe` | Reinstall with the probe extra: `uv tool install --editable ".[probe]"` |
| `login` | `skillgendev login --url http://localhost:3000/login`, sign in, close the window |
| `open` | The form is behind a click: `--open "text:Button label"` |

The probe refuses environments marked `production`; point it at dev or staging.

## Playwright's Chromium does not start

Point skillgendev at another Chromium or Chrome:

```bash
SKILLGEN_CHROMIUM=/path/to/chrome skillgendev generate --route /campaigns/new --xy
```

## An upload says "Zip must contain exactly one SKILL.md file"

You uploaded a multi-page export to a skill upload. Use `skillgendev export --one-skill --zip` for
uploads; see [Exporting](./guides/exporting.md).

## Export refuses because of the secret scan

The scan found something that looks like a key, token, real email address, phone number or
source path. Fix the source of it (often an example value in your code that reached a label or a
rule). Use reserved examples such as `name@example.com` and `555-0100`, which are allowed.

## The skill fills nothing and reports `blocked` or `changed`

That is the optional layout check declining: a dialog covers the form, or the page is not the
layout the skill was built from. The AI should inspect the page and fill with
`{"verify": false}`. If the app changed, regenerate: `skillgendev check --regenerate`.

## The docs site does not build

- `npm run build` fails on broken links and anchors on purpose. The error names the page and
  the link; fix the path (use relative `.md` links).
- An `.mdx` page breaks on `<` or `{` in prose. Wrap such text in backticks, or rename the file
  to `.md`.
- Search does not work in `npm start`: it is built at build time. Use `npm run build` and
  `npm run serve`.
