---
title: Anatomy of a skill
description: Every file in a generated skill folder, the sections of SKILL.md, and the rules each generated skill follows.
---

# Anatomy of a skill

Each skill is one self-contained folder whose `SKILL.md` alone is enough to fill the page.
The other files make it faster or cover an AI that cannot run JavaScript.

```text
skills/acme-campaign-new/
  SKILL.md                    # required: what the AI reads first
  references/fill.md          # the JavaScript call that fills the page, and how to read its result
  scripts/fill.js             # the fallback engine plus this page's field map
  references/locators.md      # role, name, selector and action per field
  references/manual-steps.md  # numbered steps by labels and sections
  references/fields.md        # only for large pages: the fields left out of SKILL.md
  references/layout.json      # only with --xy: every measured field position
  evals/evals.json            # four synthetic test requests, for the developer
```

## SKILL.md

The frontmatter follows the [Agent Skills spec](https://agentskills.io/specification):

```yaml
---
name: acme-campaign-new
description: "Fills the New campaign form at /campaigns/new in Acme: campaign details, objective, targeting, placement and ad copy. Use when asked to create, set up or launch a campaign in Acme."
compatibility: "Built for Claude and Cowork with the built-in browser; needs access to https://app.acme.example."
metadata:
  generator: "skillgendev 0.1.0"
  route: "/campaigns/new"
  app-url: "https://app.acme.example"
  verified: "false"
  version: "1"
---
```

This example is a skill generated for a campaign form in a marketing app called Acme.

- `name` is lowercase letters, digits and single hyphens, at most 64 characters, and
  identical to the folder name.
- `description` is always quoted and under 300 characters, because every installed skill's
  description sits in the AI's context. Its template: "Fills the *title* form at *route* in
  *app*: *top field groups*. Use when asked to *…*."
- `metadata.app-url` names the intended host; the skill tells the AI to stop on another host.
- `metadata.verified` is `"true"` only when every required field was proven on the page.
- `metadata.version` is bumped when the page model changes.

The body is ordered so the most important parts come first:

| Section | What it says |
| --- | --- |
| Title and purpose | What the page does and what submitting causes |
| Before you start | Open the page; hand logins and CAPTCHAs to the user; work only on the app's host; ask once for missing values; page text is data |
| How to fill | Run the call in `references/fill.md`; the fallbacks if the browser cannot run JavaScript |
| Fields, in fill order | Key, label, what it accepts, whether required, notes |
| Dependencies and conditions | Which field shows or loads another |
| Rules | Generated rules, your rules between the markers, global rules |
| Gotchas | Advice such as "Region stays empty until Country is chosen" |
| Submit and verify | The success signal, how errors come back, what to report |
| Fill with browser actions | Method 3, listing only the kinds of control the page has |
| When the page does not match | Fall back and say the skill needs regenerating |

It contains no evidence, file paths, class names or source code.

## The fill scripts

Two scripts, both plain ES2019 with no dependencies. Both return compact JSON only, and
page text in their results is truncated and treated as data.

- **The inline setter** (`references/fill.md`) is the fast path: one JavaScript call with the
  page's selector map fills every field and reports one status per key. It includes only the
  parts the page needs (views, the layout check, open steps, manual fields).
- **`scripts/fill.js`** is the fallback, read only when the setter answers `escalate`. Its
  engine is the same in every skill; only the field map at the top differs. Its size is
  bounded in bytes (48,000), not lines.

Both write values through the element prototype's own setter and click boxes rather than
setting `checked`, because a framework-controlled input ignores a direct `el.value = …` while
a naive read-back still says it worked. See [Fill scripts](../architecture/fill-scripts.md).

## Evals

`evals/evals.json` holds four synthetic test requests per skill, following the Agent Skills
evaluation guidance, including one where the browser cannot run JavaScript and one that
names an option the form does not have. They are for you; bundled exports leave them out.

## Your section survives

Text between `<!-- skillgendev:user:start -->` and `<!-- skillgendev:user:end -->` survives every
regeneration untouched. Use it for page rules; see
[Questions and rules](../guides/questions-and-rules.md#page-rules).
