---
title: Configuration
description: Every setting in .skillgendev/config.json, its default, and the environment variables skillgendev reads.
---

# Configuration

Project settings live in `.skillgendev/config.json`. `skillgendev init` creates it; you can edit it
by hand. Missing keys take their defaults. The settings are defined in
`src/skillgen/config.py` (`Settings`).

```json
{
  "schema": 1,
  "app_name": "My App",
  "app_url": "http://localhost:3000",
  "environment": "dev",
  "probe": false,
  "name_prefix": "",
  "include": [],
  "exclude": [],
  "analyzer": "claude-code",
  "concurrency": 2,
  "slice": { "depth": 3, "max_files": 40, "max_tokens": 60000 },
  "hintpacks": [],
  "skills_dir": "skills"
}
```

## Settings

| Key | Default | Meaning |
| --- | --- | --- |
| `app_name` | folder name | Display name of the app; also the default skill-name prefix (slugified). `init` without `--app-name` uses the repository folder's name |
| `app_url` | `""` | Base URL of a running dev or staging copy; empty for code-only generation. Must be an absolute `http` or `https` URL; a trailing slash is removed |
| `environment` | `dev` | `dev`, `staging` or `production`: what `app_url` points at. The probe refuses `production` |
| `probe` | `false` | Written by `init --url`, but no longer decides anything: the command alone does. A plain `generate` is always code only; `--xy` or `--url` opens a browser |
| `name_prefix` | `""` | Prefix for skill names; defaults to the slug of `app_name`, then the repository folder name |
| `include` | `[]` | Route globs to keep, such as `"campaigns/*"` (empty keeps all) |
| `exclude` | `[]` | Route globs to drop |
| `analyzer` | `claude-code` | Who performs the analysis: `claude-code` (headless `claude -p`), `file` (Claude Code writes `analysis.json` in your session), `replay` (recorded analyses) |
| `concurrency` | `2` | Routes analysed at the same time in batch mode (at least 1) |
| `slice.depth` | `3` | Import hops followed from the route's entry file |
| `slice.max_files` | `40` | Most files in a page slice |
| `slice.max_tokens` | `60000` | Most estimated tokens of code in a slice |
| `hintpacks` | `[]` | Extra hint-pack folders, relative to the repository, loaded after the shipped ones |
| `skills_dir` | `skills` | Where public skill folders are written, relative to the repository |

An invalid value fails with a `ConfigError` (exit code 2) that names it.

## Command-line overrides

Flags on a command take precedence over `config.json` for that run:

| Setting | Flag |
| --- | --- |
| `app_url` | `generate --url` (implies `--xy`, and saves the address to `config.json` for next time) |
| `name_prefix` | `generate --name`, `routes --name`, `init --name` |
| `include`, `exclude` | `routes` / `generate --include`, `--exclude` |
| `analyzer` | `generate --analyzer`, `init --analyzer` |
| `concurrency` | `generate --concurrency` |

## Your own hint packs

Point `hintpacks` at a folder in your repository to teach skillgendev your router without
changing skillgendev:

```json
{ "hintpacks": ["tools/skillgendev-hintpacks"] }
```

See [Hint packs](./hint-packs.md).

## Environment variables

| Variable | Effect |
| --- | --- |
| `SKILLGEN_CHROMIUM` | Path to a Chromium or Chrome binary to use instead of Playwright's own; useful when Playwright's Chromium does not match its version |

The variable's prefix comes from the tool name constant, like every other name skillgendev
derives.
