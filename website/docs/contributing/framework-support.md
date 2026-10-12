---
title: Adding framework support
description: Teach skillgendev a new router or folder convention with a YAML hint pack, a tiny fixture app and a test - no Python needed.
---

# Adding framework support

You do not need to touch Python to teach skillgendev a new router. Add a YAML hint pack, a tiny
example app and a test.

## 1. Write the pack

- `hintpacks/folders/<name>.yml` for a folder-routing convention: which folder, which file names
  are pages, how parameters are written, and with `requires_any` which files mark a project
  root.
- `hintpacks/routers/<name>.yml` for an ast-grep rule that matches route declarations, plus
  which metavariables hold the path and the component.

The format, with examples, is in [Hint packs](../reference/hint-packs.md). Try your ast-grep
rule against a sample file first with the `ast-grep` command line (installed with skillgendev).

## 2. Add a tiny example

Add a minimal app under `tests/fixtures/hintpacks/<id>/` with a route or two, written the way the
framework's documentation writes them. Use synthetic names only.

## 3. Add a test case

Add a case in `tests/test_hintpacks.py` that loads your pack and checks the routes (and
components) it finds in your example, then run:

```bash
uv run pytest tests/test_hintpacks.py
```

## Things the scanners already handle

- Dependency and build folders (`node_modules`, `dist`, hidden folders) are never searched.
- Parameter segments in any common form (`:id`, `[id]`, `[...slug]`, `{id}`, `<int:id>`, `$id`)
  become `:name`.
- A component name is resolved to a file through the code graph, so a pack never describes
  import syntax. When a component declares no symbol of its own name (a `.vue` file), it is linked
  by file name.
- A route the developer gives as a concrete page (`/audiences/7`) is linked to your pattern
  (`/audiences/:id`); the pattern with the most fixed segments wins.

## When a pack is not the answer

If your stack declares routes in a way no rule can match, skillgendev already asks Claude Code to
read the code graph's likely router files (`routes --all --ask-claude`), so a missing pack never
blocks anyone. A pack only makes that step cheaper and exact.

## A whole new stack

A new example app in a stack the fixtures do not cover is welcome too: add the app under
`tests/fixtures/<app>/`, its recorded analysis in `analyses/`, and its expected skills in
`expected/` (generated with `uv run pytest --update-golden` and reviewed).
