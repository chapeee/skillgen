---
title: Keeping skills current
description: Find skills made stale by code changes with skillgendev check, and regenerate only those.
---

# Keeping skills current

A skill describes a page as its code was. After you change the code, find the skills that
went stale and regenerate only those:

```bash
skillgendev check --since HEAD~1             # list stale skills
skillgendev check --since HEAD~1 --regenerate
```

## How staleness is decided

1. skillgendev lists the files changed since the git reference (default `HEAD~1`), plus
   uncommitted and untracked files.
2. With the code graph, it finds every file that depends on a changed file within **two
   hops**.
3. A skill is stale when its saved page slice (`.skillgendev/pages/<skill>/slice.json`) touches
   any of those files.

`--no-graph` matches changed files against the slices only, without following dependencies.

`check` exits with code **1** when something is stale and **0** when nothing is, so it works as
a CI gate or a git hook.

## Regenerating

`--regenerate` recreates the stale skills without asking: the flag is the go-ahead, so no
`--overwrite` is needed. As with every regeneration:

- Notes in each skill's user section are kept.
- A skill is replaced only when the new one passes every check.
- When the page model changed, its version in the skill's metadata is bumped, and
  `.skillgendev/pages/<skill>/changes.json` records what changed.

`--replay-dir` passes recorded analyses when the analyzer is `replay` (tests).

## What changed: the semantic diff

skillgendev compares the old and new page models and names meaningful changes rather than
text differences: a field added or removed, required flipped, options changed, a dependency
changed, the success signal changed. The index page marks regenerated skills.

## Run it in CI

Because `check` fails when a skill is stale, a CI step can remind you to regenerate:

```yaml
- run: skillgendev check --since origin/main
```

Regenerating in CI needs Claude Code available to the runner, so most teams list stale
skills in CI and regenerate locally with `/skillgendev`.

## The code graph cache

skillgendev keeps the Graphify code graph in `.skillgendev/cache/`. The cache records a snapshot
of Graphify's input files and ignore configuration, and is rebuilt when they change. Files
skillgendev writes itself (the skills folder, `.skillgendev/`, the index) are never treated as app
code, so generating skills does not invalidate the graph.
