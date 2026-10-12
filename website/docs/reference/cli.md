---
title: Command reference
description: Every skillgendev command and flag, with examples, shared options and exit codes.
toc_max_heading_level: 3
---

# Command reference

Every command is a `command_<name>` function in `src/skillgen/cli.py`, registered in
`HANDLERS`. This page lists every command and flag. For each command's `--json` output see
[JSON output](./json-output.md).

## Shared options

Every command accepts:

| Option | Effect |
| --- | --- |
| `--json` | Print JSON, validated against `src/skillgen/schema/cli/<command>.schema.json` before it is printed |
| `--root FOLDER` | Repository root (default: the current folder, or the nearest parent holding `.skillgendev/`) |
| `-v`, `-vv` | More output on the console: info, then debug. The log file always gets everything |

`skillgendev --version` prints the version.

## Exit codes

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | `EXIT_OK` | The command ran and everything passed |
| 1 | `EXIT_FAILED` | The command ran but something failed (a check, a stale skill, a missing tool) |
| 2 | `EXIT_ERROR` | An expected error stopped it (a `SkillgenError`: bad config, unknown route, export refused…) |
| 3 | `EXIT_NEEDS` | The run stopped at a next step for the agent or developer; see `next` |

## Set up

### `init`

Create `.skillgendev/` with its `config.json`, `routes.json`, `rules/`, `pages/` and a
`.gitignore` for `secrets/`, `cache/` and `logs/`.

| Flag | Effect |
| --- | --- |
| `--app-name "My App"` | The app's display name; also the default skill-name prefix |
| `--url URL` | Base URL of a running dev or staging copy, for `--xy` |
| `--environment dev\|staging\|production` | What `--url` points at. The probe refuses `production` |
| `--name PREFIX` | Prefix for every skill name |
| `--analyzer claude-code\|file\|replay` | Who performs the analysis step |

```bash
skillgendev init --app-name "My App" --url http://localhost:3000
```

### `install`

Add `/skillgendev`, the route-analyzer subagent and the driver skill to Claude Code, and
download Chromium for `--xy` when the probe extra is installed.

| Flag | Effect |
| --- | --- |
| `--target FOLDER` | Claude folder (default `~/.claude`; use `./.claude` for one project) |
| `--no-chromium` | Skip the Chromium download |

### `doctor`

Check Python, Graphify, Claude Code, ast-grep and Playwright, and where `skillgendev` runs from.
Exits 1 when a required check fails.

| Flag | Effect |
| --- | --- |
| `--fix` | Download Chromium for the probe |

### `login`

Open a browser window so you can log in to your dev copy once. The session is saved in
`.skillgendev/secrets/storage-state.json` for probing. Needs the probe extra.

| Flag | Effect |
| --- | --- |
| `--url URL` | Login page (default: the app URL) |

## Find pages

### `routes`

Find routes from every source and write `.skillgendev/routes.json`. See
[Route discovery](../concepts/route-discovery.md).

| Flag | Effect |
| --- | --- |
| `--all` | Every route (the default) |
| `--route /x` | Add a route by hand; repeatable |
| `--include GLOB` | Route glob to keep, such as `'campaigns/*'`; repeatable |
| `--exclude GLOB` | Route glob to drop; repeatable |
| `--name PREFIX` | Prefix for every skill name |
| `--no-graph` | Do not build the code graph |
| `--ask-claude` | Also let Claude Code list routes from the code graph's likely router files |
| `--no-claude` | Never call Claude Code, even when no route is found |

## Make skills

### `generate`

Generate one skill per route. Exits 3 when a route waits for a next step. See
[Generating skills](../guides/generating-skills.md).

| Flag | Effect |
| --- | --- |
| `--route /x` | One route, a concrete page, or its skill name. Exclusive with `--all` |
| `--all` | Every route in `routes.json` |
| `--name NAME` | With `--route`: the exact skill name. With `--all`: the prefix for every skill |
| `--xy` | Also measure where each field sits on the dev copy; only adds |
| `--url URL` | Base URL of a running dev or staging copy; implies `--xy` |
| `--open STEP` | With `--route`: what to click before the form shows, a CSS selector or `text:Label`; repeat for several; saved to `routes.json` |
| `--code-only` | Never open a browser (the default) |
| `--analyzer claude-code\|file\|replay` | Who performs the analysis |
| `--replay-dir FOLDER` | Recorded analyses for `--analyzer replay` |
| `--concurrency N` | Routes analysed at once |
| `--description "…"` | Use this skill description instead of the generated one |
| `--include GLOB`, `--exclude GLOB` | Keep or drop routes; repeatable |
| `--force` | Also retry routes marked as having no form |
| `--overwrite` | Recreate skills that already exist; without it they are left as they are and reported |
| `--no-graph` | Skip the code graph; slice entry files only |

```bash
skillgendev generate --route /campaigns/new --name new-campaign
skillgendev generate --all --name myapp --xy
skillgendev generate --route /ads/manager --name ad-budget --xy --open "text:Ad sets" --open "text:Edit budget"
```

### `prepare`

Write the slice and the analysis prompt for one route, so Claude Code can analyse it in your
session. `/skillgendev` runs it for you.

| Flag | Effect |
| --- | --- |
| `--route /x` | The route (required) |
| `--name NAME` | The skill name for this route |
| `--no-graph` | Skip the code graph |

## Answer and refine

### `questions`

List facts skillgendev needs you to confirm.

| Flag | Effect |
| --- | --- |
| `--skill NAME` | Only this skill's questions |
| `--all` | Include answered questions |

### `answer <id> <answer>`

Record an answer: `yes`, `no`, `code`, `page`, or a value. It applies on the next `generate`.
See [Questions and rules](../guides/questions-and-rules.md#answering).

```bash
skillgendev answer q1a2b3c "text:Audience settings"
```

### `add-rule [skill] "<rule>"`

Add a rule to one skill's user block, or to every skill with `--global`.

| Flag | Effect |
| --- | --- |
| `--check "KEY CONDITION"` | A machine check compiled into `fill.js`, such as `'utm_campaign ^[a-z0-9_]+$'` or `'daily_budget min 10'` |
| `--global` | Add to `.skillgendev/rules/global.md` for every skill |

```bash
skillgendev add-rule new-campaign "Daily budget must be at least 10" --check "daily_budget min 10"
skillgendev add-rule "Never launch a campaign without a UTM tag" --global
```

## Check and share

### `validate [skill…]`

Check skill folders against the Agent Skills spec and skillgendev's rules, and scan them for
secrets. With no names, every skill is checked. Size notes are reported but never fail.

### `index`

Write `skills-index.html` (graph and skill cards) and `skills-index.json` at the repository
root.

### `check`

List skills made stale by code changes. Exits 1 when something is stale. See
[Keeping skills current](../guides/keeping-current.md).

| Flag | Effect |
| --- | --- |
| `--since REF` | Git reference to compare with (default `HEAD~1`) |
| `--regenerate` | Regenerate the stale skills |
| `--replay-dir FOLDER` | Recorded analyses, when the analyzer is replay |
| `--no-graph` | Match changed files against slices only |

### `export`

Copy skills out for sharing, after checks and a secret scan, with `MANIFEST.sha256`. See
[Exporting](../guides/exporting.md).

| Flag | Effect |
| --- | --- |
| `--zip` | Write one zip file |
| `--one-skill` | Bundle every page into one skill with one `SKILL.md`, for an upload; written to `dist/skill/<name>` |
| `--plugin` | Lay out as a Claude Code plugin |
| `--name NAME` | Plugin or skill name (default: the app's prefix) |
| `--out FOLDER` | Destination (default `dist/<name>`) |

### `export-chatgpt`

Pack every page into one ChatGPT skill (one `SKILL.md` plus a file per page, with
`plugin.json` and an icon), after the same checks and scan.

| Flag | Effect |
| --- | --- |
| `--zip` | Write one zip file, ready to upload |
| `--name NAME` | Plugin and skill name (default: the skill prefix) |
| `--out FOLDER` | Destination (default `dist/chatgpt/<name>`) |

## When something goes wrong

### `logs`

Show the latest run log, or a list. Every command writes one to `.skillgendev/logs/`.

| Flag | Effect |
| --- | --- |
| `--list` | List recent logs instead |
| `--lines N` | Lines of the latest log to show (default 60) |
| `--count N` | Logs to list (default 10) |

### `probe`

Probe one route on a running dev copy and save what it saw. Only for looking; it does not
change a skill. Needs the probe extra.

| Flag | Effect |
| --- | --- |
| `--route /x` | The route (required) |
| `--url URL` | Concrete page URL, for routes with parameters |
