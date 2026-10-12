---
name: {{tool}}
description: "Drives the {{tool}} compiler, which turns a web app's code into one Agent Skill per page so Claude can fill that page's form. Use when the user asks to generate, update, check or export page or form skills for their app."
---

# {{tool}}: generate page skills from an app's code

{{tool}} reads an app's code route by route and writes one skill folder per page
(`SKILL.md` + `scripts/fill.js`). Anyone can then fill that page in Claude or Cowork with
the built-in browser, with few tokens. It works for any framework and any app.

## Commands
- `{{tool}} init [--app-name "Acme"] [--url http://localhost:3000] [--name acme]`
- `{{tool}} routes --all [--include "admin/*"] [--route /extra] --json`
- `{{tool}} generate --route /x [--name my-skill] [--overwrite] [--xy [--open STEP]] --json`
- `{{tool}} generate --all [--name acme] [--overwrite] [--xy] --json`
- `{{tool}} prepare --route /x --json` → writes the analysis prompt only, without generating.
- `{{tool}} questions --json`, `{{tool}} answer <id> "<answer>"`
- `{{tool}} login --url <page>` → opens a browser window; the user signs in and closes it.
- `{{tool}} add-rule <skill> "<rule>" [--check "key ^A"]`, or `--global`
- `{{tool}} validate`, `{{tool}} doctor [--fix]`
- `{{tool}} export [--zip] [--plugin]` → for Claude, Cowork or Claude Code;
  `{{tool}} export-chatgpt [--zip] [--name acme]` → one ChatGPT plugin.

## Naming
The user chooses skill names. With one route, `--name` is the exact skill name. With
`--all`, `--name` is the prefix for every skill (`acme` → `acme-signup`). Names must be
lowercase letters, digits and single hyphens, at most 64 characters.

## Run, then follow `next` until nothing is left
{{tool}} never asks on its own; it has no terminal to ask from. When a route cannot
finish, its result has status `needs` (or `exists`) and a `next` object, and the exit
code is 3. Do what `next` says, then run its `then` command. Repeat until no result has
a `next`, or the user says no.

- `"action": "analyse"`: {{tool}} could not run the analysis itself (for example Claude
  Code is not signed in). Do it yourself: read `prompt` and the files it lists, read-only,
  following the imports they point to. Write one JSON object matching the schema in the
  prompt to `write`. Then run `then`; {{tool}} uses your analysis while the code is
  unchanged. For several routes, use one `{{tool}}-route-analyzer` subagent per route.
- `"action": "ask"`: only the user can decide or do this. Ask them `ask` in chat, as a
  question, in your own words if that is clearer.
  - On yes, run `run` when it is not empty, then run `then`.
  - `need` `limit`: the AI's own limit is reached and `ask` says when it resets. Tell
    the user, and stop. Do not read the code and write the analysis yourself: that
    spends far more of the same limit. Run `then` once the limit has reset; the
    analysis already done is reused.
  - `need` `url`: their answer is the address; put it in place of `<url>` in `then`.
  - `need` `login`: `run` opens a browser window and waits until the user signs in and
    closes it, so give it a long timeout. Never type their password yourself.
  - `need` `overwrite`: the skill exists; `then` recreates it. Notes in its user section
    are kept.
  - `need` `open`: the form's fields are hidden behind a click. Their answer is the
    text of the button, tab or link; put it in place of `<label>` in `then`.
  - `need` `server` or `probe`: the user starts their dev server or reinstalls; wait
    until they say it is done, then run `then`.
  - On no, stop that route and say what was left undone.

Answering open questions and generating again is the user updating a skill they made,
so pass `--overwrite` then.

## Rules
- Never edit the app's source while analysing.
- Never copy real personal data or secrets into an analysis or a skill.
- Facts you deduce go in `inferred`; {{tool}} keeps uncertain facts out of skills until the
  developer confirms them.
- When you analyse a page yourself, describe every part hidden until a click (wizard
  steps, tabs, accordion panels, dialogs) as `views`, in fill order, each with the click
  that reaches it from the part before; the prompt says how. You never write click code:
  {{tool}} walks the views in Chromium with `--xy`, measures every field, and the skill
  walks them the same way when it fills the page.
- A running app is optional. A normal `generate` reads code only. Add `--xy` to also
  measure where each field sits (x/y) on the dev copy; it only adds and never removes a
  field. If the form appears only after a click, add `--route … --open STEP` (a CSS
  selector or `text:Label`); it is saved, and the skill makes the same click. Dev or
  staging only; submits are intercepted.
