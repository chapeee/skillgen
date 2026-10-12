---
title: Working in Claude Code
description: The /skillgendev command, the route-analyzer subagent and the driver skill that skillgendev install adds to Claude Code.
---

# Working in Claude Code

The recommended way to generate skills is from inside Claude Code. Claude reads each
page's code in your session, runs skillgendev's commands, follows each result's next step and
asks you only what needs a decision.

## Install the integration

```bash
skillgendev install                       # into ~/.claude
skillgendev install --target ./.claude    # into this project only
skillgendev install --no-chromium         # skip the Chromium download
```

`install` copies three files from the package's `claude/` folder, with the tool name filled
in:

| File | What it is |
| --- | --- |
| `commands/skillgendev.md` | The `/skillgendev` slash command |
| `agents/skillgendev-route-analyzer.md` | A subagent that analyses one route with read-only tools (Read, Grep, Glob, Write) |
| `skills/skillgendev/SKILL.md` | The driver skill: how to run skillgendev and follow its `next` steps |

When the probe extra is installed, `install` also downloads Chromium for `--xy`. Rerun it
after updating skillgendev; it copies the files rather than linking them.

:::note Any agent can drive skillgendev
The driver instructions are plain Markdown (`claude/skills/driver/SKILL.md` in the
repository), so any agent that can run commands can follow them. `install` only sets them
up for Claude Code.
:::

## Use `/skillgendev`

```text
/skillgendev /campaigns/new
/skillgendev all
/skillgendev all --name acme
```

What the command does, in order:

1. If `.skillgendev/config.json` does not exist, it runs `skillgendev init` and asks you for the
   app's display name and, if you have one, a dev URL.
2. For `all`, it runs `skillgendev routes --all --json`, shows you the routes, and lets you drop
   or rename any before generating.
3. It runs `skillgendev generate --route <route> --json` (or `--all`), passing `--name` through,
   and `--xy` when you want field positions.
4. It follows each result's `next` until nothing is left:
   - `analyse`: Claude reads the prompt and writes the analysis itself, using one
     route-analyzer subagent per route when there are several.
   - `ask`: Claude asks you the question in chat, runs `run` on a yes, then runs `then`.
   - status `exists`: Claude asks before a skill is recreated.
5. It reports each skill folder and any open questions, asks you those questions, records
   your answers with `skillgendev answer`, and generates again with `--overwrite`.

## How the analysis runs

There are three analyzers, set with `--analyzer` or in `config.json`:

| Analyzer | Who reads the code | Used by |
| --- | --- | --- |
| `claude-code` (default) | skillgendev runs headless `claude -p` with read-only tools (`Read`, `Grep`, `Glob`) and a JSON schema, one route per run | `generate` in a terminal or CI |
| `file` | Claude Code writes `analysis.json` itself in your session | interactive `/skillgendev` |
| `replay` | recorded analyses named `<route-slug>.json` | tests and fixtures |

If skillgendev cannot call Claude Code itself (not installed, not signed in), the run does
not fail. It writes the prompt, and the result carries `next.action: "analyse"` with the
prompt and the path to write. The agent running skillgendev does the analysis and runs the
command again. See [The agent handoff](../concepts/agent-handoff.md).

If Claude's own usage limit is reached, the result says so with `need: "limit"`. The agent
tells you and stops, rather than reading the code by hand, which would spend far more of
the same limit. Run `then` once the limit has reset; finished analyses are reused.

## `prepare`: just the prompt

```bash
skillgendev prepare --route /campaigns/new
```

`prepare` builds the page slice and writes the analysis prompt to
`.skillgendev/pages/<skill>/prompt.md` without generating anything. `/skillgendev` runs it for
you; you rarely need it by hand.
