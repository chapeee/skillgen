---
title: Development setup
description: Clone the repository, sync every extra with uv, and install your working copy as a global skillgendev command.
---

# Development setup

You need Python 3.10 or newer and [uv](https://docs.astral.sh/uv/). Node.js is only needed for
the documentation site and for CI's `node --check` on the bench script.

```bash
git clone https://github.com/chapeee/skillprinter
cd skillprinter
uv sync --all-extras                 # core, probe and ast-grep extras, dev tools
uv run playwright install chromium   # only for browser tests and the probe
```

`uv sync --all-extras` installs the dev group too: mypy, pytest, ruff, and the PyYAML and
jsonschema type stubs.

## Use your working copy everywhere

To try your clone as a global `skillgendev` command in other projects (like `npm link`):

```bash
scripts/install-local.sh            # macOS, Linux
.\scripts\install-local.ps1         # Windows PowerShell (add -RunTests to run all checks)
```

Code edits apply at once, because the install is editable. Rerun the script after changing
dependencies or `pyproject.toml`. See [Installation](../getting-started/installation.md#one-step-local-install)
for its options.

## Repository layout

```text
src/skillgen/      the package (see Architecture)
claude/            /skillgendev command, route-analyzer agent, driver skill
hintpacks/         framework knowledge as YAML: folders/, routers/
tests/             unit tests, tests/fixtures/ (example apps), tests/bench/ (test page)
docs/              spec.md, decisions.md
scripts/           install-local.ps1 / install-local.sh
website/           this documentation site and the landing page
.github/workflows/ ci.yml (library checks), docs.yml (this site)
```

## Tooling

| Tool | Command | Settings |
| --- | --- | --- |
| ruff (lint) | `uv run ruff check .` | Line length 100, Python 3.10 target, Google docstrings, many rule sets including `T20` (no print), `BLE` (no blind except), `ANN` and `D` |
| ruff (format) | `uv run ruff format .` | Double quotes |
| mypy | `uv run mypy` | `strict = true` over `src` and `tests` |
| pytest | `uv run pytest` | Browser and Claude tests excluded by default |

`cli.py` is exempt from the no-print rule. Tests are exempt from docstring and annotation
rules.

## Running skillgendev from the clone

```bash
uv run skillgendev doctor
uv run skillgendev routes --all --no-claude --root ../my-app
```

`--root` points any command at another project. It goes after the command name, like every
shared option. Avoid running commands against `tests/fixtures/` directly: they would write a
`.skillgendev/` workspace into the fixtures. The tests copy fixtures to a temporary folder first.
