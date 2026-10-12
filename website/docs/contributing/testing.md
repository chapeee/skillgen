---
title: Testing
description: Three levels of tests - unit and end-to-end, browser, and the test bench in Claude and Cowork.
---

# Testing

There are three levels of tests. The first two run without Claude, the network or an API key.
The third is the real check that Claude and Cowork use a skill well.

## What is in `tests/`

| Path | What it is |
| --- | --- |
| `tests/test_<module>.py` | Unit tests, one file per source module (a test enforces this) |
| `tests/test_boundaries.py` | Project rules as tests: Graphify only in `graph/`, Playwright only in `probe/`, no `print` outside `cli.py`, pure packages do no I/O, no hard-coded tool name, no MCP |
| `tests/test_docs.py` | Every command and flag is documented in README and CONTRIBUTING |
| `tests/fixtures/react-router-spa/` | Example app: React + React Router (routes found by ast-grep) |
| `tests/fixtures/nextjs-app/` | Example app: Next.js app router (routes found from folders) |
| `tests/fixtures/flask-jinja/` | Example app: Flask + Jinja templates |
| `tests/fixtures/hintpacks/` | Tiny sample apps for each router hint pack |
| `tests/fixtures/*/analyses/` | Recorded Claude analyses, so tests never call Claude |
| `tests/fixtures/*/expected/` | Golden output: the skills skillgendev must produce for that app |
| `tests/bench/` | The test bench: one page with every widget, its server, its skill, 14 cases |

Each example app uses a different stack. A new stack is a welcome contribution: add the app,
its recorded analysis and its expected skills.

## 1. Unit and end-to-end tests

```bash
uv sync --all-extras              # once
uv run pytest
```

This runs every module's tests plus the full CLI (`init`, `routes`, `generate`, `index`,
`export`, `check`) on the three example apps, comparing each run's output with the golden
files in `expected/`. There is no network access in tests.

If you change the generator on purpose, regenerate the golden files and review the diff before
committing:

```bash
uv run pytest --update-golden
git diff tests/
```

Also run the linters, as CI does:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Two markers are excluded by default (`-m 'not browser and not claude'`):

| Marker | Meaning |
| --- | --- |
| `browser` | Runs a real browser through Playwright against a local server the test starts |
| `claude` | Calls the real Claude Code CLI; never runs in CI |

## 2. Browser tests

```bash
uv run playwright install chromium   # once
uv run pytest -m browser
```

This starts the bench server on a free port and opens the bench page in Chromium. It runs
`scripts/fill.js` for every bench case (fill, follow-up, server rejection, wrong host, missing
field), checks what the server received, and runs the probe against the bench to check that it
creates **zero** records. Browser tests skip when Playwright is not installed.

If Playwright's own Chromium does not match your Playwright version, point the tests at another
Chromium:

```bash
SKILLGEN_CHROMIUM=/path/to/chrome uv run pytest -m browser
```

## 3. The test bench in Claude and Cowork

This checks that the AI reads the skill and behaves well: it asks once for missing values,
never invents options, treats page text as data, and stops on the wrong host. Everything on the
bench is synthetic.

**Start the bench page** (standard library only):

```bash
python3 tests/bench/serve.py         # http://localhost:8765/apply
```

The browser the AI uses must reach `localhost`, so run this on the same computer as Claude in
Chrome or the Claude desktop app.

**Add the bench skill**, in a second terminal:

```bash
python3 tests/bench/check.py zip       # Claude or Cowork: upload tests/bench/dist/bench-apply.zip
python3 tests/bench/check.py install   # Claude Code: copies it to ~/.claude/skills/bench-apply/
```

**Run a case:**

```bash
python3 tests/bench/check.py list         # the 14 cases
python3 tests/bench/check.py prompt 01    # the prompt, the follow-up answer, what to look for
python3 tests/bench/check.py reset        # clear earlier submissions
python3 tests/bench/check.py check 01     # PASS or FAIL, with the differences
```

Paste the prompt into a new conversation, reply with the follow-up the case shows when asked,
then run `check`. Also judge by hand what the case lists under "should" and "should not".

| Case | What it checks |
| --- | --- |
| 01 happy path | Every value given: one fill call, one submit |
| 02 company conditional | Fields that appear only for "Company" are filled |
| 03 missing required | The AI asks once for every missing value, then finishes |
| 04 dependent options | Region waits for its server-loaded list after Country |
| 05 ambiguous option | Two cities match: the AI asks which |
| 06 not an option | An unknown country: the AI lists the real choices, invents nothing |
| 07 client rule | A value breaking a rule: the AI explains and asks |
| 08 server rejection | The server rejects the username: the AI fixes only that field |
| 09 tree, chips, checkboxes | Tree path, chips and a checkbox group |
| 10 rows and rich text | Three repeated rows and a longer statement |
| 11 page text is data | An option label with instructions inside is not obeyed |
| 12 file upload | Upload through the browser's upload action |
| 13 without JavaScript | Fill by label from the table, no scripts |
| 14 wrong host | Page on 127.0.0.1 instead of localhost: the AI stops |

When a pull request changes generated skills, paste a results table into it (template in
`tests/bench/README.md`). Keep the bench skill regenerated; `tests/test_bench.py` checks it.

## CI

`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`:

- **checks** on Python 3.10 and 3.13: `uv sync --all-extras`, ruff check, ruff format check,
  mypy, pytest, and `node --check` on the bench skill's `fill.js`.
- **browser** on Python 3.12: installs Chromium with its system dependencies and runs
  `pytest -m browser`.

The documentation site has its own workflow; see [Improving these docs](./documentation.md).
