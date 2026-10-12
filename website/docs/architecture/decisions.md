---
title: Design decisions
description: A guided summary of the decision log - the choices that shape skillgendev and why they were made.
---

# Design decisions

The design is in [`docs/spec.md`](https://github.com/chapeee/skillgen/blob/main/docs/spec.md)
(Code-to-Skill Compiler, Final Spec v2). Decisions that change it are logged, newest first, in
[`docs/decisions.md`](https://github.com/chapeee/skillgen/blob/main/docs/decisions.md)
with date, decision, why and the alternatives considered. **If the two disagree, the decision
log wins.**

This page summarises the decisions that most shape how skillgendev behaves. Read the log for
the full reasoning and measurements.

## Project overrides

- **No MCP anywhere.** The library does not depend on, install or mention MCP servers, and
  generated skills never mention them.
- **Skills target any AI that accepts Agent Skills**, with its built-in browser and nothing
  installed, so they never rely on one product's tool names.
- **Code-only generation is the default.** The Playwright probe is an optional extra and runs
  only with `--xy` (or `--url`).
- **Users choose skill names** with `--name`.

## How skills are built and used

| Decision | Why |
| --- | --- |
| `SKILL.md` carries an inline setter; `fill.js` is the fallback | Pointing at `fill.js` made the reader pay for the engine twice. One bench fill went from 10,869 to 3,877 tokens |
| The fill call moves to `references/fill.md`; `SKILL.md` is ordered for truncation | The most important instructions survive if a reader truncates |
| The script budget is bytes, not lines | Bytes are what a reader pays for; a line cap was met by packing lines |
| Four fill methods in every skill | Not every AI's browser can run JavaScript in a page |
| Selectors, not coordinates or accessibility names, address fields | Coordinates go stale and reflow; on the bench 7 of 21 fields had no unique accessible name |
| An optional layout check verifies the page before writing | A skill should not type into the wrong form; a failed check writes nothing |
| The measured layout ships, readable, as `references/layout.json` | The AI can check by hand when the automatic check declines |

## How generation behaves

| Decision | Why |
| --- | --- |
| Commands never ask; an existing skill needs `--overwrite` | Every command is run by an agent with no terminal to answer from |
| A stopped run says what comes next, and the next run continues | No work is thrown away; analysis is reused |
| Two modes: normal (code only) and `--xy` (normal plus x/y) | `--xy` can only add, so it is never worse than a normal run |
| x/y problems never cost the code skill | The skill is written from the code, then the agent asks |
| The AI's own limit is a wait, not work to do by hand | Reading the code by hand would spend far more of the same limit |
| A page is sliced from its own component, never from the router | A router file would pull every sibling page into the slice |
| The browser stops rediscovering what the code states | The old controller walk took most of a probe's time and found less than the code; revealing fields from the code's own conditions halved bench time with the same result |
| The analysis is shown the live page when a capture matches the route | It no longer guesses fields from source alone, and a capture from another route is dropped |
| Generated output does not invalidate the source graph | Generating skills should not force a graph rebuild |

## Exports

| Decision | Why |
| --- | --- |
| A skill upload takes one skill; a plugin may hold many | Products refuse a multi-`SKILL.md` archive; `--one-skill` bundles |
| The ChatGPT export is one skill with a file per page | Same rule; the entry point stays about 25 lines |
| Every plugin's author is `chapeee` | The maintainer's decision; no flag changes it |

## Open questions

The log keeps open questions at the top. At the time of writing they include:

1. **Descriptive facts below 0.7.** Facts that change how a field is filled become questions
   below 0.7; descriptive text below 0.7 is dropped from `SKILL.md` without a question.
2. **Host check in `fill.js`.** It compares hostnames, not ports, so a skill survives a dev
   server's port changing.
3. **Folder routing as data** in `hintpacks/folders/*.yml`, read by one generic scanner.
4. **No `verify` command yet.** The spec's with-and-without-skill runs need a browser in
   headless Claude Code, which would need an MCP server. Skills ship `evals/evals.json` and the
   bench has manual cases instead.
5. **The final name.** The spec recommends "Formcast"; it stays `skillgendev` until decided.

## Proposing a decision

Open an issue, or a pull request that adds an entry to `docs/decisions.md` with the date, the
decision, why, and the alternatives you considered. When the spec is unclear, ask before
building.
