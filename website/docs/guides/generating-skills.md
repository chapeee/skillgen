---
title: Generating skills
description: Generate one skill or every skill, choose names, recreate skills safely, and reuse analysis.
---

# Generating skills

`skillgendev generate` is the main command. It turns one route, or every route in
`.skillgendev/routes.json`, into a skill folder.

```bash
skillgendev generate --route /campaigns/new --name new-campaign    # one route
skillgendev generate --all --name myapp                  # every route
```

`--route` accepts a route pattern, a concrete page address, or the route's skill name.

## Naming skills

You always choose the names.

| Command | Name |
| --- | --- |
| `--route /campaigns/new --name new-campaign` | exactly `new-campaign` |
| `--all --name acme` | `acme-<route-slug>` for every route, such as `acme-campaign-new` |
| no `--name` | prefix from `config.json` `app_name`, else the repository folder name |

Every name is checked against the Agent Skills rules: lowercase letters, digits and single
hyphens, at most 64 characters, and identical to its folder. A name that does not pass is
rejected with a clear message. You can also edit `skill` per route in `routes.json`; a
name you chose is locked (`"name_locked": true`) and survives later `routes --all` runs.
Clashing generated names get a numeric suffix (`-2`, `-3`).

## Concrete pages and patterns

You can give a real page address instead of the pattern. With
`--route /campaigns/42/edit`, skillgendev finds the code of
`/campaigns/[id]/edit` and reads that. The pattern with the most fixed segments
wins. If two patterns fit equally well, skillgendev guesses nothing and the analysis starts
with no files; give the pattern route then.

## What a run reports

Each route ends with one status:

| Status | Meaning |
| --- | --- |
| `written` | The skill folder was written and passed every check |
| `no-form` | The page has no editable controls; it is listed in the index and skipped |
| `invalid` | A check failed; the previous skill and its page data were left untouched |
| `failed` | The route could not be processed |
| `skipped` | `"skip": true` in `routes.json` |
| `exists` | A skill is already there; nothing was done (see below) |
| `needs` | The run stopped at something the agent or you do next (exit code 3) |

Routes marked as having no form are skipped on later runs; `--force` retries them.

## Recreating a skill

A skill that already exists is never replaced by accident. Without `--overwrite`,
`generate` stops before any analysis or probing and reports status `exists`, and
`/skillgendev` asks you whether to recreate it.

```bash
skillgendev generate --route /campaigns/new --name new-campaign --overwrite
```

- Your notes between the `skillgendev:user:start` and `skillgendev:user:end` markers are kept.
- A recreated skill replaces the old one only when it passes every check. If a check fails,
  the old skill and its saved page data stay exactly as they were.
- If nothing was generated, `routes.json` is restored exactly, so a `--name` rename does
  not stick for a run that wrote nothing.

## Analysis is reused

If the page's code has not changed since the last analysis, skillgendev reuses it instead of
asking Claude again, so recreating a skill after answering questions is quick and costs
no tokens.

The reuse key is a fingerprint of everything the analysis is given: the rendered prompt
(route, skill, app context, any probe summary and Graphify's account of the page), the answer
schema, and the bytes of every file in the page's slice. When any of those changes, the page
is analysed again. To force a fresh analysis, delete
`.skillgendev/pages/<skill>/analysis.json`. Recorded analyses
(`--analyzer replay`) are never reused, so tests stay exact.

## Other options

| Flag | Effect |
| --- | --- |
| `--xy` | Also measure where each field sits on a dev copy. See [Field positions](./xy-layout.md) |
| `--url URL` | The dev copy's address; implies `--xy` |
| `--open STEP` | With `--route`: what to click before the form shows. See [Hidden forms](./hidden-forms.md) |
| `--code-only` | Never open a browser (the default) |
| `--description "…"` | Use this description instead of the generated one |
| `--include GLOB` / `--exclude GLOB` | Keep or drop routes, such as `'campaigns/*'` |
| `--concurrency N` | Routes analysed at once in batch mode (default from config: 2) |
| `--analyzer`, `--replay-dir` | Choose the analyzer; see [Working in Claude Code](./claude-code.md#how-the-analysis-runs) |
| `--no-graph` | Skip the code graph and slice the entry files only |

The full list, with every command, is in the [CLI reference](../reference/cli.md).

## Size limits

A `SKILL.md` body must stay under 500 lines; about 5,000 tokens is the budget. When a page
has many fields, skillgendev first moves optional fields into `references/fields.md`, four at
a time, and says in `SKILL.md` when to read it. Going over the token budget is reported as
a note, never a failure.
