---
title: Adding or changing a command
description: The five things every new command or flag needs in one pull request, and where each existing command lives.
---

# Adding or changing a command

Every command is a `command_<name>` function in `src/skillgen/cli.py`, registered in
`HANDLERS`. In the same pull request:

1. Add `command_<name>` and its parser in `cli.py`, and register it in `HANDLERS`.
2. Add `src/skillgen/schema/cli/<name>.schema.json` for its `--json` output.
3. Add tests.
4. **Document it for users** in the README's *Command reference*, every flag included.
5. **Document it for maintainers** in CONTRIBUTING's "Commands: where each one lives" table.

`tests/test_docs.py` fails when a command or flag is missing from either document, and
`tests/test_cli.py` fails when a command has no schema. Please update this site's
[command reference](../reference/cli.md) and [JSON output](../reference/json-output.md) pages
too.

## Rules a command follows

- **It never prompts or waits for input.** An agent runs it. If it needs the developer, it does
  all it can, then reports a `next` step (exit code 3). See [The agent handoff](../concepts/agent-handoff.md).
- **Replacing existing output is the one decision that stops before any work**, and it takes a
  flag for the answer (like `--overwrite`).
- **It returns a `Reply`**: `data` for `--json`, `lines` for text, `is_ok`, `needs_action`.
  Only `cli.py` prints.
- **It raises `SkillgenError` subclasses** for expected failures (exit code 2).
- **Its `--json` output matches its schema**, or `emit` replaces it with an internal error.

## Where each command lives

| Command | Main code | Tests |
| --- | --- | --- |
| `init` | `workspace.py`, `config.py` | `test_cli.py`, `test_workspace.py`, `test_config.py` |
| `routes` | `pipeline.discover_routes`, `routes/`, `graph/hubs.py`, `pipeline.ask_claude_for_routes` | `test_folders.py`, `test_astgrep.py`, `test_hintpacks.py`, `test_hubs.py`, `test_cli.py` |
| `prepare` | `pipeline.prepare_route`, `analyze/prompt.py` | `test_cli.py`, `test_prompt.py` |
| `generate` | `pipeline.analyze_route` / `finish_route`, `compile/`, `generate/`, `validate/`; `--overwrite` in `cli.hold_existing_skills`; `--xy` in `cli._layout_measurer` → `probe.runner.measure_page_layout`; `--open` in `cli._with_open_steps` → `pipeline.apply_open_steps`; `next` in `cli.describe_next_step` → `handoff.build_next_step` | `test_fixtures.py`, `test_merge.py`, `test_pipeline.py`, `test_handoff.py`, `test_cli.py` |
| `questions`, `answer` | `cli.py`, `compile/assess.py` | `test_cli.py`, `test_assess.py` |
| `add-rule` | `generate/user_rules.py` | `test_user_rules.py`, `test_fixtures.py` |
| `validate` | `validate/spec.py`, `validate/scan.py` | `test_spec.py`, `test_scan.py` |
| `index` | `generate/index_page.py`, `pipeline.write_index` | `test_index_page.py`, `test_cli.py` |
| `check` | `drift/check.py`, `drift/diff.py` | `test_check.py`, `test_diff.py`, `test_cli.py` |
| `export` | `export.py` | `test_export.py`, `test_cli.py` |
| `export-chatgpt` | `export.export_chatgpt_plugin` | `test_export.py`, `test_cli.py` |
| `probe`, `login` | `probe/runner.py` (Playwright, lazily imported) | `test_probe_runner.py` (`-m browser`) |
| `logs` | `logs.py` | `test_logs.py` |
| `install` | `claude/` (shipped as package data); Chromium in `cli.install_chromium` | `test_cli.py` (never downloads) |
| `doctor` | `cli.py` | `test_cli.py` |
