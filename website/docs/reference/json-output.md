---
title: JSON output
description: The --json payload of every command, validated against its schema before it is printed.
---

# JSON output

Every command accepts `--json`. Its output is an object with `ok` (boolean) and `command`
(the command name), plus the command's own fields. Before printing, skillgendev validates it
against `src/skillgen/schema/cli/<command>.schema.json`. If the payload does not match, that
is a bug in skillgendev, and it prints this instead of bad JSON:

```json
{ "ok": false, "command": "generate", "error": "internal: output does not match its schema: …" }
```

An expected error (exit code 2) prints `ok: false` with an `error` message.

This is the interface an agent builds on. Read each command's schema file for exact types;
the summary below lists the fields.

## Fields by command

| Command | Fields besides `ok` and `command` |
| --- | --- |
| `init` | `root`, `config`, `app_name`, `app_url`, `is_new` |
| `routes` | `routes[]` (`route`, `skill`, `title`, `sources`, `entry_files`, `has_form`, `skip`), `count`, `found` |
| `prepare` | `route`, `skill`, `skill_exists`, `skill_folder`, `prompt`, `prompt_path`, `schema_path`, `analysis_path`, `slice` |
| `generate` | `results[]` (see below), `written`, `invalid`, `no_form`, `failed`, `exists`, `needs`, `open_questions` |
| `questions` | `questions[]` (`id`, `skill`, `subject`, `text`, `choices`, `answer`), `open` |
| `answer` | `id`, `skill`, `answer` |
| `add-rule` | `skill`, `rule`, `check`, `global`, `path` |
| `validate` | `results[]` (`skill`, `ok`, `problems`, `notes`) |
| `index` | `html`, `json`, `skills`, `fields` |
| `check` | `since`, `changed_files`, `stale`, `unknown`, `regenerated` |
| `export` | `path`, `skills`, `files`, `plugin`, `skill` (the bundled name; empty without `--one-skill`) |
| `export-chatgpt` | `path`, `skills`, `files`, `plugin` |
| `probe` | `route`, `skill`, `url`, `fields`, `proven`, `conditions`, `dependencies`, `capture` |
| `login` | `url`, `storage_state` |
| `logs` | `logs`, `latest`, `tail` |
| `install` | `target`, `installed`, `chromium` |
| `doctor` | `checks[]` (`name`, `ok`, `detail`, `required`), `fixed` |

## `generate` results

Each entry of `results`:

| Field | Type | Meaning |
| --- | --- | --- |
| `route` | string | The route |
| `skill` | string | The skill name |
| `status` | enum | `written`, `no-form`, `invalid`, `failed`, `skipped`, `exists`, `needs` |
| `problems` | string[] | Failed checks and notes |
| `open_questions` | integer | Questions waiting for the developer |
| `skill_folder` | string | Where the skill was written |
| `verified` | boolean | Every required field was proven on the page |
| `measured_fields` | integer | Fields that got x/y with `--xy`; 0 otherwise |
| `next` | object | Present when the route stopped; see [The agent handoff](../concepts/agent-handoff.md) |

`next` always has all eight keys: `action` (`analyse` or `ask`), `need`, `reason`, `ask`,
`run`, `then`, `prompt`, `write`.

## Example: an agent loop

```bash
skillgendev generate --all --json > result.json
echo $?          # 3 when any route has a next step
```

```python
import json, subprocess

result = subprocess.run(
    ["skillgendev", "generate", "--all", "--json"], capture_output=True, text=True
)
payload = json.loads(result.stdout)
for item in payload.get("results", []):
    step = item.get("next")
    if step and step["action"] == "ask":
        print(item["route"], "→", step["ask"])
```

## Other schemas

`src/skillgen/schema/` also holds the schemas for skillgendev's internal documents:

| Schema | For |
| --- | --- |
| `page.schema.json` | `page.json`, the page model |
| `page-analysis.schema.json` | What Claude Code returns for one page |
| `route-listing.schema.json` | What Claude Code returns when it lists routes |
