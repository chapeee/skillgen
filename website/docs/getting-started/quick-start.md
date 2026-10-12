---
title: Quick start
description: From an app repository to a validated skill folder, inside Claude Code or in batch.
---

# Quick start

This walks you from your app's repository to a validated skill for one page. Run every
command from your project's root folder.

:::info Commands are run by an agent
skillgendev's commands are designed to be run by an AI agent such as Claude Code, which
reads skillgendev's instructions, runs the commands and asks you whatever needs a decision.
You can run them yourself too; nothing ever waits for input.
:::

## 1. Initialise the workspace

```bash
cd ~/code/my-app
git init                          # only if the project is not a git repository yet
skillgendev init --app-name "My App"
```

`init` creates `.skillgendev/`, skillgendev's working folder. Commit it; its `secrets/`, `cache/`
and `logs/` folders are ignored by the `.gitignore` it writes. Git is optional, but with it
skillgendev records which commit each skill was made from and [`check`](../guides/keeping-current.md)
can tell which skills went stale.

Add `--url http://localhost:3000` if you have a dev copy and want field positions later.

## 2. Find the routes

```bash
skillgendev routes --all
```

This writes `.skillgendev/routes.json`. Open it to check what was found:

- Add a missing route with `skillgendev routes --route /path`.
- Set `"skip": true` on a route you do not want.
- Edit a `skill` name to choose it yourself.

Folders such as `node_modules` and `dist` are never searched. See
[Route discovery](../concepts/route-discovery.md) for every source.

## 3. Generate a skill

Choose one way.

### A. Inside Claude Code (recommended to start)

```bash
skillgendev install
claude
```

Then type `/skillgendev /campaigns/new` (one page) or `/skillgendev all` (every page). Claude does the
reading in your session, follows each result's next step, and asks you questions in chat.

### B. Batch

skillgendev calls `claude -p` once per route:

```bash
skillgendev generate --route /campaigns/new --name new-campaign    # one route, exact skill name
skillgendev generate --all --name myapp                  # every route, names start with myapp-
```

Either way you get `skills/<name>/` with `SKILL.md`, `scripts/fill.js`, references and
evals.

## 4. Answer open questions

Facts the code leaves unclear stay out of the skill until you answer:

```bash
skillgendev questions
skillgendev answer q1a2b3c "yes"
skillgendev generate --all --overwrite
skillgendev validate
```

`--overwrite` is needed because the skill already exists; your notes in its user section
are kept. See [Questions and rules](../guides/questions-and-rules.md).

## 5. Use the skill

Pick the export for where the skill is going:

| Destination | Command |
| --- | --- |
| Claude or ChatGPT skill upload | `skillgendev export --one-skill --zip`, then upload `dist/skill/<name>.zip` |
| Claude Code or Cowork on your machine | copy a folder from `skills/` into `~/.claude/skills/` |
| A plugin | `skillgendev export --plugin --zip` or `skillgendev export-chatgpt --zip` |

Then ask the AI to fill the page. It opens the page in its built-in browser and uses the
skill. See [Using generated skills](./using-skills.md) and [Exporting](../guides/exporting.md).

## 6. Keep skills current

```bash
skillgendev check --since HEAD~1 --regenerate
skillgendev index                    # skills-index.html: every skill and a graph of the app
```

## Next

- Add field positions with [`--xy`](../guides/xy-layout.md).
- Forms behind a button, tabs or a wizard: [Hidden forms and views](../guides/hidden-forms.md).
- Something went wrong: [Logs and debugging](../guides/logs-and-debugging.md).
