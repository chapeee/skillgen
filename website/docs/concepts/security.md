---
title: Security and privacy
description: Skills hold no credentials, probing never writes data, exports are scanned, and evidence stays on the developer's machine.
---

# Security and privacy

**Skills hold no credentials, and generation never writes data.**

| Risk | Control |
| --- | --- |
| Credentials in a skill | Skills contain URLs, labels, selectors and rules only. The login used for probing is a Playwright storage-state file in `.skillgendev/secrets/`, gitignored and never exported |
| Probing creates or changes data | The probe runs only against environments marked dev or staging and refuses `production`. Write requests are intercepted and cancelled, nothing is submitted, and clicks such as Save, Delete or Sign out are never made |
| Real personal data in skills | Probe captures keep request body shapes (keys and types), never values. Example values are synthetic, built from each field's constraints. `export` scans for keys, tokens, emails and phone numbers and fails when it finds any |
| Wrong environment at use time | `metadata.app-url` names the intended host. The skill tells the AI to stop if the tab is on another host and to confirm before submitting on a production site |
| Wrong host at fill time | `scripts/fill.js` refuses to run when the page's hostname differs from the skill's `app-url` hostname. It compares hostnames, not ports, so the same skill works when a dev server's port changes |
| Passwords and secrets | Secret fields use the `steps` strategy: the user types them. Skills never ask for or fill a secret |
| Destructive actions | Skills cover filling and saving forms only |
| Prompt injection from page text | The skill tells the AI to treat option labels and error messages as data. The fill scripts return them as JSON strings, truncated |
| Tampered skill folder | `export` writes `MANIFEST.sha256` with a hash of every file |
| Source code leaking to clients | Skills carry no file paths, class names or code; evidence stays in `.skillgendev/`. The export scan also flags source file paths |

An honest limit: a skill shows its reader the page's field names and route, which the
reader's own browser already exposes.

## Analysis is read-only

Headless analysis runs `claude -p` with only the `Read`, `Grep` and `Glob` tools, so Claude
cannot edit your code while it reads it. The route-analyzer subagent may write exactly one
file: the analysis JSON at the path it was given.

## What to commit, and what never to commit

| Path | Commit? |
| --- | --- |
| `.skillgendev/config.json`, `routes.json`, `questions.json`, `pages/`, `rules/` | Yes |
| `.skillgendev/secrets/` (login state) | **Never**; ignored by the generated `.gitignore` |
| `.skillgendev/cache/`, `.skillgendev/logs/` | No; ignored |
| `skills/`, `skills-index.html` | Your choice; this is the public output |
| `.env`, Playwright storage-state files anywhere | **Never** |

## Reporting a vulnerability

Please do not open a public issue for a security problem. Contact the maintainer through
the repository on GitHub first.
