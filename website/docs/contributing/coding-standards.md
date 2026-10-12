---
title: Coding standards
description: Naming, function size, docstrings, errors, logging, data and the generated-output rules every change follows.
---

# Coding standards

These rules apply to every change. When a rule and a request conflict, ask first.

## Language

Python 3.10+. Code must run on 3.10: no `match` relying on 3.11-only features, no
`typing.Self`, no `ExceptionGroup`.

## Naming

- Modules are lowercase nouns: `slice.py`, `confidence.py`.
- Functions are snake_case and start with a verb: `find_routes`, `build_page_model`,
  `write_skill`.
- Classes are PascalCase nouns (`PageModel`, `FieldSpec`); constants are `UPPER_SNAKE`.
- Booleans start with `is_`, `has_` or `should_`.
- No abbreviations except `url`, `id`, `json`, `html`, `api`. `config` is allowed only as the
  module name; in code write `settings`, never `cfg`, `btn`, `el`, `opts`, `idx`.
- Tests: `tests/test_<module>.py`, named `test_<function>_<behaviour>`, such as
  `test_combine_confidence_caps_disagreeing_sources`.

## Functions

- One job each, about 40 lines at most. Split when longer.
- Type hints on every argument and return value. No `Any` without a comment saying why.
- `model/`, `compile/` and `generate/` are pure: no file, network, subprocess, clock or
  environment access.
- Prefer frozen dataclasses for data. No global mutable state.

## Docstrings and comments

- A Google-style docstring on every public function and class: what it does, `Args:`,
  `Returns:`, `Raises:` (omit a section only when it is empty).
- Comments explain *why*, never *what*.
- No commented-out code.
- A TODO names an issue: `# TODO(#12): support multi-route wizards`.

## Errors and output

- Custom exceptions live in `errors.py` and inherit from `SkillgenError`.
- Never a bare `except:`, and never `except Exception:` without re-raising or a comment saying
  why it is safe.
- Log with `logger = logging.getLogger(__name__)`; only `cli.py` prints.
- Every command supports `--json`, validated against `schema/cli/<command>.schema.json`.
- Log what a developer needs to debug a run: inputs, counts, timings, external calls and their
  errors. Never log secrets or personal data.

## Startup cost

Every command pays for whatever `skillgen.cli` imports. `jsonschema` (about 320 ms) and
`PyYAML` (about 80 ms) are imported where they are used, and `tests/test_boundaries.py` fails
if either reaches the startup path.

## Data

- Every fact records its source and confidence (see [The page model](../concepts/page-model.md)).
- Evidence (file paths, line numbers, probe captures) stays in `.skillgendev/` and never reaches
  `SKILL.md`, `fill.js` or anything `export` writes.
- No secrets or real personal data in fixtures, output or logs.

## The name

The public name is `skillgendev`; the import package is `skillgen`. Use the constant `skillgen.TOOL_NAME` instead of writing the name
in strings, so a rename is one commit.

## Generated `SKILL.md`

- Passes the Agent Skills spec: `name` is lowercase letters, digits and single hyphens, at
  most 64 characters, identical to its folder name.
- `description` is always quoted in YAML and under 300 characters.
- Body under 500 lines (and about 5k tokens).
- No evidence, file paths, class names or source code.
- Text between the `skillgendev:user:start` and `skillgendev:user:end` markers survives
  regeneration untouched.

## Fill scripts

Plain ES2019 with no dependencies, compact JSON output, size measured in bytes. See
[Fill scripts](../architecture/fill-scripts.md).
