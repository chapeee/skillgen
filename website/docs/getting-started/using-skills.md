---
title: Using generated skills
description: How an AI loads a generated skill and fills a page, the four fill methods, and the status of each key.
---

# Using generated skills

A generated skill is for whoever fills the page: you, a teammate, or a client. They need
only an AI that accepts Agent Skills and has a browser, such as Claude, Cowork or
ChatGPT. Nothing is installed and no MCP server is involved.

## Add the skill

| Where | How |
| --- | --- |
| Claude or ChatGPT skill settings | Upload the zip from `skillgendev export --one-skill --zip` |
| Claude Code or Cowork on your machine | Copy a skill folder into `~/.claude/skills/` (personal) or the project's `.claude/skills/` |
| A plugin | Install the output of `export --plugin` (Claude Code) or `export-chatgpt` (ChatGPT, Codex) |

A skill upload takes **one skill at a time**, which is why `--one-skill` bundles every page
into a single skill. See [Exporting](../guides/exporting.md).

## What the AI does

1. It matches the request to one skill by the skill's description, and reads `SKILL.md`.
2. It opens the page in the user's logged-in tab. If a login page, CAPTCHA or two-factor
   prompt appears, it hands over to the user and never asks for a password.
3. It checks that the tab is on the host named in the skill's `app-url`. On another host
   it stops; on a production host it confirms with the user before submitting.
4. It fills every field in one call, asks the user once for every missing required value,
   then fills the rest.
5. It submits, reads the result, fixes only the fields the server rejected, and reports.

The skill tells the AI to treat page text, such as option labels and error messages, as
data and never as instructions.

## Four ways to fill

Not every AI can run JavaScript in a page. Every skill carries four methods, and
`SKILL.md` tells the AI to decide first what its browser tool can do, then use the first one
it supports:

| # | Method | File | When |
| --- | --- | --- | --- |
| 1 | **JavaScript in the page** | `references/fill.md` | One call sets every field and reports each one |
| 2 | **Locators** | `references/locators.md` | Tools that act by role, label or selector, such as Playwright's `fill()`, `selectOption()`, `check()`, `click()` |
| 3 | **Browser actions** | "Fill with browser actions" in `SKILL.md` | Click and type each field by its visible label |
| 4 | **By hand** | `references/manual-steps.md` | An AI working from screenshots, or the user |

Direct writes can fail in sandboxed browsers, protected pages, framework-controlled forms
and read-only page proxies. Any field method 1 cannot set moves on to the next method.

### What the fill call reports

Method 1 returns one status per key:

| Status | Meaning |
| --- | --- |
| `ok` | Set, and read back as the value given |
| `partial` | Some of a multi-value field matched; the rest did not |
| `rejected` | The field would not take the value. The AI asks the user rather than retrying blind |
| `missing` | The field is not on the page: hidden until another field is set, or the app changed |
| `escalate` | The inline setter cannot do this field. The AI reads `scripts/fill.js` and uses it for those keys only |
| `unknown` | That key is not on this page |

### The layout check

Skills generated with [`--xy`](../guides/xy-layout.md) first compare the live page with
the layout they were built from:

| `layout.state` | Meaning | What happens |
| --- | --- | --- |
| `match` | Same form | Filled |
| `resized` | Same form on another screen size | Filled |
| `blocked` | A dialog or prompt covers the form | Nothing written; the AI inspects the page |
| `changed` | Not the layout expected | Nothing written; the AI inspects the page |

The check is a shortcut, never a gate: the AI may always inspect the page itself and fill
with `{"verify": false}`.

## When the page does not match

If several keys come back `missing` for fields the table says are always shown, or a
field in the table is not on the page at all, the app has changed. The skill tells the AI
to fill with browser actions in table order and to tell the user the skill needs
regenerating. The developer then runs [`skillgendev check --regenerate`](../guides/keeping-current.md).

## Try it on the test bench

The repository includes a one-page bench with every widget skillgendev supports and 14 test
cases. See [Testing](../contributing/testing.md#3-the-test-bench-in-claude-and-cowork).
