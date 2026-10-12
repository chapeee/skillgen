---
title: Installation
description: Install skillgendev from PyPI with uv, pipx or pip, and check its tools with skillgendev doctor.
---

# Installation

skillgendev is published on [PyPI](https://pypi.org/project/skillgendev/).

## Requirements

| Tool | Why | Required |
| --- | --- | --- |
| Python 3.10 or newer | skillgendev is a Python package | Yes |
| [uv](https://docs.astral.sh/uv/) or pipx | installs it as a tool in its own environment | Recommended |
| git | in your app, lets skillgendev record the source commit and detect stale skills | Recommended |
| [Claude Code](https://claude.com/claude-code) | reads each page's code; batch generation calls `claude -p` | For generation |
| Chromium (via Playwright) | only for `--xy`, `probe` and `login` | Optional |

Graphify (the code graph), PyYAML, jsonschema and ast-grep (`ast-grep-cli`) are installed
with skillgendev as normal dependencies.

## Install

```bash
uv tool install "skillgendev[probe]"
skillgendev doctor --fix
```

- On macOS or Linux you can use [Homebrew](https://brew.sh) instead:
  `brew install chapeee/tap/skillgendev` (includes the probe extra; upgrade with
  `brew upgrade skillgendev`).
- `uv tool install` puts `skillgendev` on your `PATH`. `pipx install "skillgendev[probe]"`
  or `pip install "skillgendev[probe]"` work too.
- Upgrade later with `uv tool upgrade skillgendev`.
- The `probe` extra adds Playwright, which `generate --xy` needs to measure where each
  field sits on a running dev copy. Leave it out for code-only use:
  `uv tool install skillgendev`
- `skillgendev doctor --fix` checks every tool and downloads Chromium for the probe.
  `skillgendev install` downloads it too.
- `.[astgrep,probe]` from older notes still works; ast-grep is now a core dependency.

### From a clone (for contributors)

```bash
git clone https://github.com/chapeee/skillprinter.git
cd skillprinter
uv tool install --editable ".[probe]"
```

`--editable` means a `git pull` in the clone updates your `skillgendev` at once.

### One-step local install

The repository ships a script that works like `npm link`. It removes any old install,
clears uv's cache for the package, installs your clone globally in editable mode, checks
that `skillgendev` points at your clone, and downloads Chromium.

```powershell
.\scripts\install-local.ps1
```

```bash
scripts/install-local.sh
```

| PowerShell | bash | Effect |
| --- | --- | --- |
| `-RunTests` | `--run-tests` | Also run the checks |
| `-NoExtras` | `--no-extras` | Install without the probe extra |
| `-SkipChromium` | `--skip-chromium` | Do not download Chromium |
| `-Uninstall` | `--uninstall` | Remove the global install |

Rerun it after changing dependencies or `pyproject.toml`. If PowerShell blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-local.ps1
```

## Set up Claude Code

Batch generation (`generate --all`) calls Claude Code headless. Install it and sign in
once by running `claude`. To add the `/skillgendev` command, its subagent and its driver
skill to Claude Code:

```bash
skillgendev install
```

Run `skillgendev install` again after you update skillgendev, because it copies the
instructions rather than linking them. See [Working in Claude Code](../guides/claude-code.md).

## Check the install

```bash
skillgendev doctor
skillgendev --version
```

`doctor` reports each tool with a mark: `✓` found, `✗` missing and required, `·` missing
but optional.

| Check | Required | Purpose |
| --- | --- | --- |
| `python` | Yes | 3.10 or newer |
| `skillgendev` | Yes | the version, and the folder it runs from |
| `graphify` | Yes | code graph (core) |
| `claude` | No | Claude Code for batch analysis |
| `ast-grep` | No | router hint packs (installed with skillgendev) |
| `playwright` | No | runtime probe (probe extra) |

`doctor` exits with code 0 when every required check passes.

:::tip On Windows
Use PowerShell. Git Bash rewrites arguments that start with `/` into Windows paths, so
`--route /campaigns/new` arrives as `C:/Program Files/Git/campaigns/new`. See
[Troubleshooting](../troubleshooting.md#git-bash-rewrites-routes).
:::
