---
title: Workspace files
description: What skillgendev writes into your repository - the internal .skillgendev/ workspace and the public skills/ output.
---

# Workspace files

skillgendev writes two kinds of output into your repository: an internal workspace that never
leaves your machine, and public skill folders.

```text
.skillgendev/                         # internal: never exported
  config.json                      # settings (see Configuration)
  routes.json                      # every route, its skill name and code files
  questions.json                   # facts waiting for you
  route-listing-prompt.md          # what Claude was asked when it listed routes
  rules/global.md                  # rules copied into every skill
  pages/<skill>/
    prompt.md                      # what Claude was asked about this page
    analysis.json                  # what Claude answered
    analysis.fingerprint           # what the saved analysis was made from
    request.fingerprint            # the last analysis request
    slice.json                     # the files that build the page
    page.json                      # the merged page model
    evidence.jsonl                 # where each fact came from
    changes.json                   # what changed since the last run
    probe/                         # what the probe saw
  cache/                           # code graph and other caches        (gitignored)
  logs/                            # one log per command, newest 30     (gitignored)
  secrets/                         # login state for probing            (gitignored)
  .gitignore
skills/                            # public: one folder per route
  <skill>/SKILL.md …
skills-index.html                  # the index page with the graph
skills-index.json                  # the same data, machine-readable
```

## The workspace root

Commands find the workspace by walking up from the current folder to the first one holding
`.skillgendev/config.json`. `--root` points at another project.

## What to commit

Commit `.skillgendev/` (its own `.gitignore` keeps `secrets/`, `cache/` and `logs/` out), so
your team shares routes, names, answers, rules and analyses. Whether you commit `skills/` and
the index is your choice: they are the public output.

## Files are written atomically

Every file is written to a temporary file and moved into place, so a reader never sees a
half-written file. Text is always written with `\n` line endings, so a skill has the same
bytes on every platform and its export manifest matches.

## Files skillgendev never treats as app code

The skills folder, `.skillgendev/` and the index files are excluded from the code graph, so
generating skills never makes your code look changed.

## Route entries

See [Route discovery](../concepts/route-discovery.md#merging-into-routesjson) for the
`routes.json` entry format and which keys you may edit.
