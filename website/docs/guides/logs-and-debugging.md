---
title: Logs and debugging
description: Every command writes a full debug log; per-route files show what Claude was asked, what it answered and what was merged.
---

# Logs and debugging

Every command writes a full debug log in your project, so anyone running skillgendev can see
exactly what happened and share it.

```bash
skillgendev logs                     # the latest log (last 60 lines) and its path
skillgendev logs --lines 200         # more of it
skillgendev logs --list              # recent logs
skillgendev logs --list --count 20
skillgendev generate --all -v        # also print progress to the terminal (-vv for debug)
```

- Logs live in `.skillgendev/logs/`, named like `20261008-091500-generate.log`. The newest 30
  are kept. They are gitignored and never exported.
- They record the version, your command, timings, the files sliced for each route, each
  Claude Code call (prompt size, exit code, error output), what the merge kept, and every
  check that failed.
- On an error, skillgendev prints `Full log: <path>`.
- The console shows warnings by default, info with `-v`, and debug with `-vv`. The log file
  always gets everything.

## Per-route files

When a page's skill looks wrong, read its folder in `.skillgendev/pages/<skill>/`:

| File | What it tells you |
| --- | --- |
| `prompt.md` | What Claude was asked, including the answer schema |
| `analysis.json` | What Claude answered |
| `slice.json` | Which files it read |
| `page.json` | The merged page model |
| `evidence.jsonl` | Where each fact came from |
| `changes.json` | What changed since the last run |
| `probe/` | What the probe saw, after `probe` or `--xy` |

For route discovery, `.skillgendev/route-listing-prompt.md` holds what Claude was asked when it
listed routes from the code graph.

## Reading a stopped run

A run that cannot finish a route does not fail silently. Its text output says why and what
to do next, and `--json` carries the same as a `next` object with exit code 3. See
[The agent handoff](../concepts/agent-handoff.md).

## Common fixes

See [Troubleshooting](../troubleshooting.md) for the problems people meet most: routes
mangled by Git Bash, Claude Code not signed in, no fields measured, and more.
