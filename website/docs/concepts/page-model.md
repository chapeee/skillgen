---
title: The page model
description: page.json, fill strategies and value types, and how sources and confidence decide which facts reach a skill.
---

# The page model

Everything known about one route's form is merged into one internal document,
`.skillgendev/pages/<skill>/page.json` (schema `src/skillgen/schema/page.schema.json`). Skills
are generated from it, and it never leaves your machine.

## What it holds

| Part | Meaning |
| --- | --- |
| `route`, `skill`, `title`, `purpose` | The page, its skill name and what it is for |
| `app`, `source_commit`, `version` | The app, the commit it was made from, and the model version |
| `sections` | Visible groups of fields (a fieldset, a card, a tab) |
| `fields` | Every editable control, keyed by a stable field key |
| `fill_order`, `dependencies` | The order to fill in, and which field controls which |
| `groups` | Repeating rows, such as several ad creatives or audience rules |
| `rules` | Rules a value must follow, in words, optionally as a machine check |
| `gotchas` | Advice the AI should know, each with its provenance |
| `submit` | The submit control, the success signal and where field errors show |
| `params` | Route parameters such as `id` in `/campaigns/:id/edit` |
| `open` | Clicks that show a form hidden behind a button |
| `views` | Parts shown only after clicks: wizard steps, tabs, dialogs |
| `layout` | Measured field boxes, with `--xy` only |
| `verified` | `true` only when every required field was proven on the running page |

Each field carries its label, what it means, its type, whether it is required, any
`required_if` or `visible_if` condition, its options or where options load from, limits
(length, range, pattern, file types), the selector used to find it, and its fill strategy.

### Fill strategies

| Strategy | Used for |
| --- | --- |
| `native-input` | Text, number, email, date and similar inputs, textareas |
| `native-select` | `<select>`, single or multiple |
| `choice` | Checkbox and radio groups |
| `aria-combobox` | Searchable dropdowns and autocompletes: type, wait, pick by visible text |
| `aria-tree` | Tree pickers: expand nodes along a path, pick the item |
| `aria-listbox` | Custom lists and chip pickers |
| `rich-text` | Content-editable editors |
| `file` | Uploads; needs the browser tool's file-upload action |
| `steps` | Anything else, handled by the user or the browser tool |

`file` and `steps` fields cannot be completed by the fill script on its own; the skill tells
the AI how to handle them.

### Value types

`text`, `long-text`, `number`, `date`, `email`, `url`, `phone`, `enum`, `multi-enum`,
`boolean`, `file`, `path` (a tree path). Conditions compare a controlling field with the
operators `in`, `not_in`, `checked` and `filled`.

## Sources

Every fact records where it came from:

| Source | Meaning | Base confidence |
| --- | --- | --- |
| `RUNTIME_PROBED` | Seen on the running page by the probe | 0.90 |
| `EXTRACTED` | Stated literally in code (an attribute, a validator entry) | 0.85 |
| `CLAUDE_INFERRED` | Claude's reading of the code, not stated literally | 0.60 |
| `DEVELOPER_CONFIRMED` | Answered by the developer | 1.00 |
| `USER_DEFINED` | A rule added by hand or with `add-rule` | 1.00 |

## Confidence

The arithmetic lives in `src/skillgen/model/confidence.py`:

- **Agreeing sources combine** as `1 − (1 − a)(1 − b)`. Code plus probe gives
  `1 − 0.15 × 0.10 = 0.985`.
- **Disagreeing sources** cap the fact at **0.5** and raise a question.
- **Facts at 0.7 or above** go into the skill. Below that they wait for the developer.

So a fact Claude only deduced (0.60) never reaches a skill on its own; it becomes a question,
unless the probe or the code confirms it. Descriptive facts (what a field means, its format,
notes) never raise questions.

Your answer turns a fact into `DEVELOPER_CONFIRMED` at 1.0. See
[Questions and rules](../guides/questions-and-rules.md).

## Evidence

Beside each fact, skillgendev keeps evidence: the subject (such as `field:email.required`), the
source, a location (a file and line, or a probe capture id) and short detail, in
`.skillgendev/pages/<skill>/evidence.jsonl`. Evidence never reaches `SKILL.md`, `fill.js` or
anything `export` writes.
