---
title: FAQ
description: Short answers about what skillgendev is, what it supports, and what it costs.
---

# FAQ

## What does skillgendev produce?

One [Agent Skills](https://agentskills.io/specification) folder per page of your app, with a
`SKILL.md` that tells an AI what every field means, what it accepts, the fill order, the rules,
and how to fill and check the page. See [Anatomy of a skill](./concepts/skill-anatomy.md).

## Which AIs can use the skills?

Any AI that accepts Agent Skills and has a browser: Claude, Cowork, ChatGPT and others. Each
skill carries four fill methods, so it works whether or not the AI's browser can run
JavaScript in the page.

## Does it need an MCP server, an extension or an API key at use time?

No. Skills use the AI's built-in browser and nothing installed. The library never depends on
or mentions MCP servers.

## Which frameworks are supported?

Any web app whose forms render as HTML in a browser. Frameworks matter only for finding routes;
see [Route discovery](./concepts/route-discovery.md). When no hint pack matches, Claude Code
reads the code graph to find routes.

## Do I need a running copy of my app?

No. Generation reads code only by default. A dev or staging copy is needed only for `--xy`,
which adds field positions and a layout check.

## Is it safe to point the probe at my app?

Only at dev or staging. The probe refuses an environment marked `production`, intercepts and
cancels write requests, never submits, and never clicks things like Save, Delete or Sign out.

## What does generation cost?

Only the analysis step spends model tokens: Claude Code reads up to about 60k tokens of code
per page. The spec estimates roughly 0.1 to 0.3 million tokens processed per route. Everything
else is deterministic and runs on your CPU. Analyses are reused while a page's code is
unchanged.

## How much does a skill save at fill time?

The design spec models a 40-field form at about 8 tool calls with a skill against about 138 with
computer use, roughly 25 times fewer input tokens. That is a model from the spec, not a published
measurement yet.

## Can I rename a skill?

Yes. You always choose names: `--name` on `generate`, or edit `skill` in `.skillgendev/routes.json`.
Names must be lowercase letters, digits and single hyphens, at most 64 characters.

## Will regenerating erase my edits?

Not the ones between `<!-- skillgendev:user:start -->` and `<!-- skillgendev:user:end -->`. Everything
else in `SKILL.md` is generated and is rewritten. Put your notes and rules in the user section, or
use `skillgendev add-rule`.

## Is there a `verify` command?

Not yet. The spec's with-and-without-skill runs would need a browser in headless Claude Code,
which would mean an MCP server, so it is an open question in the decision log. Each skill ships
`evals/evals.json`, and the repository's [test bench](./contributing/testing.md#3-the-test-bench-in-claude-and-cowork)
has 14 manual cases.

## Is it on PyPI?

Yes: `uv tool install "skillgendev[probe]"` or `pip install skillgendev`; see [Installation](./getting-started/installation.md).

## Why is it called skillgendev?

`skillgen` was already taken on PyPI, so the published package and command are `skillgendev`.
The name lives in one constant (`skillgen.TOOL_NAME`); the Python import package is still `skillgen`.

## What licence is it under?

Apache License 2.0.
