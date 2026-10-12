---
title: Exporting and sharing
description: Which export goes where - skill uploads, local folders, Claude Code plugins and ChatGPT or Codex plugins.
---

# Exporting and sharing

Every product has two ways in, and they want different shapes:

- A **skill upload** takes one skill at a time. Its archive must hold exactly one
  `SKILL.md`, with the skill folder as the archive's top level and no plugin manifest.
- A **plugin** may hold many skills, but needs its manifest and `skills/<name>/`.

Uploading the wrong shape fails with *"Zip must contain exactly one SKILL.md file"*.

## Which export goes where

| Where it goes | Command | What you get |
| --- | --- | --- |
| Claude or ChatGPT skill settings (upload) | `skillgendev export --one-skill --zip` | `dist/skill/<name>.zip`: `<name>/SKILL.md` plus a file per page. One skill, no manifest |
| Claude Code or Cowork on your machine | `skillgendev export` | `skills/<page>/` folders to copy into `~/.claude/skills/`. One skill per page |
| Claude Code plugin | `skillgendev export --plugin --zip` | `.claude-plugin/plugin.json` + `skills/<page>/` |
| ChatGPT and Codex plugin | `skillgendev export-chatgpt --zip` | `plugin.json` + one skill under `skills/<name>/` + `assets/icon.svg` |

`export --one-skill` and `export-chatgpt` both bundle, so both hold exactly one `SKILL.md`.
A plain `export --zip` of several pages does not, and says so when you run it.

Every export copies all [four fill methods](../getting-started/using-skills.md#four-ways-to-fill),
so the same skill works in Claude, Cowork, ChatGPT or any other AI.

## Before anything leaves your machine

Every export, of every shape:

1. **Checks** each skill against the Agent Skills spec and skillgendev's own rules.
2. **Scans** every file for secrets and personal data: private keys, AWS, GitHub, Slack,
   Anthropic or OpenAI and Google keys, JSON web tokens, bearer tokens, password
   assignments, real-looking email addresses, phone numbers and source file paths. Reserved
   example domains (`example.com`, `.test`, `localhost` and similar) and `555-01xx` numbers
   are allowed, because generated examples use them on purpose. Any finding stops the export.
3. **Writes `MANIFEST.sha256`** with a SHA-256 hash of every file, sorted by path, so a
   tampered skill folder can be detected.

Internal data never goes: `page.json`, evidence, probe captures and questions stay in
`.skillgendev/`. `evals/` is left out of bundles, because it is for you, not for the AI.

## One skill, a file per page

`--one-skill` keeps every page whole and makes the entry point cheap to read:

```text
acme/
  SKILL.md                                  # the only SKILL.md: a table of forms, ~25 lines
  references/acme-campaign-new/page.md            # that page's fields, rules and fill call
  references/acme-campaign-new/locators.md        # and its other fill methods
  references/acme-campaign-new/manual-steps.md
  references/acme-campaign-new/fields.md, layout.json
  scripts/acme-campaign-new/fill.js               # its fallback engine
  MANIFEST.sha256
```

The entry point lists each form's title, route, what is on it and the one file to read,
then says to read exactly one. A fill costs that table plus one page file, so adding pages
does not make a fill dearer. Paths inside each page's files are rewritten to match this
layout.

The folder is named after the skill (`--name`, else the app prefix), because every product
requires the folder name and the `name` in `SKILL.md` to match. With `--zip` that holds
whatever you call the file: `--out dist/download` still zips as `acme/SKILL.md`.

## Options

| Flag | `export` | `export-chatgpt` |
| --- | --- | --- |
| `--zip` | Write one zip file | Write one zip, ready to upload |
| `--name` | Plugin or bundled skill name (default: the app's prefix) | Plugin and skill name (default: the skill prefix) |
| `--out` | Destination (default `dist/<name>`; `dist/skill/<name>` with `--one-skill`) | Destination (default `dist/chatgpt/<name>`) |
| `--one-skill` | Bundle every page into one skill | always bundled |
| `--plugin` | Lay out as a Claude Code plugin | n/a |

Both plugin manifests name the author `chapeee`, the maintainer's recorded decision; no flag
changes it.

The export stops and says so when `--name` is too long: a skill name is at most 64
characters, and ChatGPT counts `<plugin>:<skill>` against that limit.

## ChatGPT and Codex

- **Skill upload:** `skillgendev export --one-skill --zip`, then upload it in ChatGPT's skill
  settings: the same file Claude takes.
- **Plugin:** `skillgendev export-chatgpt --zip` writes the portable Agent Plugins layout that
  ChatGPT and Codex share: `plugin.json` at the root (name, version, description, author, and
  the listing name, tagline and icon), one skill under `skills/<name>/`, and
  `assets/icon.svg`. Upload it at [platform.openai.com/plugins](https://platform.openai.com/plugins)
  as a skills-only plugin; OpenAI scans and reviews it before you choose to publish.

To use it yourself, copy the folder to `~/.codex/plugins/acme`, list it in
`~/.agents/plugins/marketplace.json`, restart the ChatGPT desktop app and install it from the
Plugins Directory:

```json
{
  "name": "local",
  "plugins": [
    {
      "name": "acme",
      "source": { "source": "local", "path": "./.codex/plugins/acme" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

## The skill index

```bash
skillgendev index
```

writes `skills-index.html` and `skills-index.json` at the repository root: one self-contained
page with an interactive graph of the app (app, skills, sections, fields and their
dependencies) and a card per skill. It needs no network, so it works opened from a zip.
`export` includes it.
