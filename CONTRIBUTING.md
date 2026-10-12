# Contributing to skillgendev

Thanks for helping. skillgendev turns an app's code into one Agent Skills folder per
page, so Claude or Cowork can fill that page's form with few tokens. This guide
explains how to set up, what we expect from a change, and how to test it, including
end to end in Claude or Cowork.

The design is in [`docs/spec.md`](docs/spec.md). Decisions that change it are in
[`docs/decisions.md`](docs/decisions.md). If the two disagree, the decision log wins.

## Ground rules in one minute

1. **No framework or domain knowledge in the core.** Router conventions, validation
   libraries and the like go in `hintpacks/` as YAML. Deleting `hintpacks/` must
   leave a working tool.
2. **No MCP servers, no client installs.** Generated skills run in Claude or Cowork
   with the built-in browser and nothing else.
3. **Code-only generation is the default.** The Playwright probe is optional
   (`pip install "skillgendev[probe]"`) and only runs when a dev URL is given.
4. **Every fact has a source and a confidence. Evidence never reaches a skill.**
5. **No secrets or real personal data**, anywhere: fixtures, tests, logs, examples.

## Set up

You need Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/chapeee/skillprinter
cd skillprinter
uv sync --all-extras          # core, probe and ast-grep extras, dev tools
uv run playwright install chromium   # only for browser tests and the probe
```

To try your working copy as a global `skillgendev` command in other projects (like
`npm link`), run the local install script. It clears uv's cache for the package,
installs your clone in editable mode and checks that `skillgendev` points at it:

```bash
scripts/install-local.sh            # macOS, Linux
.\scripts\install-local.ps1         # Windows PowerShell (add -RunTests to run all checks)
```

Code edits apply at once. Rerun the script after changing dependencies or
`pyproject.toml`.

## Before you open a pull request

Run all four. CI runs the same commands.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest                 # unit tests, no network, no browser
uv run pytest -m browser      # if you touched fill.js, probe/ or tests/bench/
```

If you changed anything that affects generated output, also run the bench by hand
in Claude or Cowork (see [Testing in Claude and Cowork](#testing-in-claude-and-cowork)).

## Code style

**Tooling.** Python 3.10+, uv, ruff (lint and format), mypy `--strict`, pytest.

**Layout.** Code lives in `src/skillgen/`:

| Package | What it does |
| --- | --- |
| `graph/` | Graphify adapter, page slice, change impact, likely router files (`hubs.py`). The only place that imports `graphify`. |
| `routes/` | Route probes, merge into `routes.json`, skill names |
| `probe/` | Optional Playwright probe. The only place that imports `playwright`, and only lazily. |
| `analyze/` | Prompts, `page-analysis.schema.json`, headless Claude Code runner |
| `model/` | `page.json` schema, facts, confidence |
| `compile/` | Merge facts into `page.json`; compile rules into checks |
| `generate/` | `SKILL.md`, `fill.js`, references, evals, index page |
| `validate/` | Agent Skills spec checks, model checks, secret and personal-data scan |
| `verify/` | With-skill vs without-skill runs |
| `drift/` | Stale-route check, semantic diff |
| `schema/` | JSON schemas for `page.json`, Claude's answers and every CLI `--json` output |
| `cli.py` | Argument parsing and output; the only module that prints |
| `pipeline.py` | Runs the per-route steps (files and subprocesses at the edge) |
| `handoff.py` | The `next` step a run hands to the agent or the developer, and the command to continue with |
| `logs.py` | Run logs: console level from `-v`, full debug log in `.skillgendev/logs/` |
| `export.py` | Folder, zip, Claude Code plugin and ChatGPT plugin export with `MANIFEST.sha256` |

**Naming.**

- Modules are lowercase nouns: `slice.py`, `confidence.py`.
- Functions are snake_case and start with a verb: `find_routes`, `build_page_model`.
- Classes are PascalCase nouns; constants are `UPPER_SNAKE`.
- Booleans start with `is_`, `has_` or `should_`.
- No abbreviations except `url`, `id`, `json`, `html`, `api`.
- Tests: `tests/test_<module>.py`, named `test_<function>_<behaviour>`.

**Functions.** One job each, about 40 lines at most, type hints on every argument and
return value. `model/`, `compile/` and `generate/` are pure: data in, data out. Files,
subprocesses and the network are touched only at the edges.

**Docstrings and comments.** Google-style docstrings on every public function and
class (summary, `Args`, `Returns`, `Raises`). Comments explain *why*, not *what*. No
commented-out code. A TODO names an issue: `# TODO(#42): …`.

**Errors and output.** Raise exceptions from `skillgen.errors`. Never use a bare
`except`. Log with `logging`; only `cli.py` prints. Every CLI command has `--json`,
and its output is checked against `src/skillgen/schema/cli/<command>.schema.json`.

**The page inventory.** `probe/extract.js` returns a page's fields *and* everything
clickable on it, each with a `step` that can be replayed (a selector when it names one
element, else `text:Label`). Three flags keep a reader off the wrong control, measured
on a real app where a naive click walk collected 122 fields from four different forms:
`chrome` (inside `nav`, `header`, `footer`, `aside` or a menu role), `leaves` (a link to
another path or origin) and `risky` (the label says submit, save, delete, reset, pay,
sign out and the like). On the maintainer's insurance form that turns 29 clickables into
13 worth trying; on the onboarding form, 23 into 5. Tests: `tests/test_inventory.py`.

**Startup cost.** Every command pays for whatever `skillgen.cli` imports, so
`jsonschema` (about 320ms) and `PyYAML` (about 80ms) are imported where they are used:
`schema._validator_class`, `validate.spec.check_skill_md`, `routes.astgrep` and
`routes.hintpacks`. `tests/test_boundaries.py` fails if either reaches the startup path.
Measured: `import skillgen.cli` 1.08s to 0.68s, so every command starts about 0.15s
sooner once `uv`'s own overhead is counted.

**The name.** `skillgendev` is a working name. Use the constant `skillgen.TOOL_NAME`
instead of writing the name in strings, so the rename is one commit.

## Commands: where each one lives

Every command is a `command_<name>` function in `src/skillgen/cli.py`, registered in
`HANDLERS`. Its `--json` output must match `src/skillgen/schema/cli/<name>.schema.json`.

| Command | Main code | Tests |
| --- | --- | --- |
| `init` | `workspace.py`, `config.py` | `test_cli.py`, `test_workspace.py`, `test_config.py` |
| `routes` | `pipeline.discover_routes`, `routes/`, `graph/hubs.py`, `pipeline.ask_claude_for_routes` | `test_folders.py`, `test_astgrep.py`, `test_hintpacks.py`, `test_hubs.py`, `test_cli.py` |
| `prepare` | `pipeline.prepare_route`, `analyze/prompt.py` | `test_cli.py`, `test_prompt.py` |
| `generate` | `pipeline.analyze_route` / `finish_route`, `compile/`, `generate/`, `validate/`; `--overwrite` in `cli.hold_existing_skills`; `--xy` in `cli._layout_measurer` → `probe.runner.measure_page_layout`; `--open` in `cli._with_open_steps` → `pipeline.apply_open_steps`; stops and `next` in `cli.find_stops_before_work`, `cli.finish_analysed`, `cli.describe_next_step` → `handoff.build_next_step`; analysis reuse in `pipeline.find_reusable_analysis` | `test_fixtures.py`, `test_merge.py`, `test_pipeline.py`, `test_handoff.py`; `--overwrite`, `next` and exit code 3 in `test_cli.py` |
| `questions`, `answer` | `cli.py`, `compile/assess.py` | `test_cli.py`, `test_assess.py` |
| `add-rule` | `generate/user_rules.py` | `test_user_rules.py`, `test_fixtures.py` |
| `validate` | `validate/spec.py`, `validate/scan.py` | `test_spec.py`, `test_scan.py` |
| `index` | `generate/index_page.py`, `pipeline.write_index` | `test_index_page.py`, `test_cli.py` |
| `check` | `drift/check.py`, `drift/diff.py` | `test_check.py`, `test_diff.py`, `test_cli.py` |
| `export` | `export.py` | `test_export.py`, `test_cli.py` |
| `export-chatgpt` | `export.export_chatgpt_plugin`: `build_chatgpt_manifest`, `retarget_skill_md`, `check_chatgpt_names` | `test_export.py`, `test_cli.py` |
| `probe`, `login` | `probe/runner.py` (Playwright, lazily imported) | `test_probe_runner.py` (`-m browser`) |
| `logs` | `logs.py` | `test_logs.py` |
| `install` | `claude/` (shipped as package data); Chromium in `cli.install_chromium`, shared with `doctor --fix` | `test_cli.py` (never downloads: `--no-chromium` or a stub) |
| `doctor` | `cli.py` | `test_cli.py` |

### Adding or changing a command

In the same pull request:

1. Add `command_<name>` and its parser in `cli.py`, and register it in `HANDLERS`.
2. Add `schema/cli/<name>.schema.json` for its `--json` output.
3. Add tests.
4. **Document it for users** in the README's *Command reference* (every flag).
5. **Document it for maintainers** in the table above.

`tests/test_docs.py` fails when a command or flag is missing from either document, and
`tests/test_cli.py` fails when a command has no schema.

### Normal and `--xy`

A skill is always built from the code alone: `pipeline.write_skill` merges with no probe,
and `prepare` gives the analysis no probe either. `--xy` then measures the code-built page
(`probe.runner.measure_page_layout`: open the page, click the route's open steps, and
measure each field by the skill's own selector with `probe/measure.js`). The measuring
function returns only a `Layout`, so `--xy` can only add x/y, never change a field.
Measuring the skill's own selectors, rather than matching what the probe finds to them,
means a box always belongs to the element the layout check reads back; a run on a real
page showed the probe naming controls `input` and `select`, which matched nothing. Without `--xy` nothing is measured and
no saved capture is read. `tests/test_cli.py` holds both guarantees, and each test was
checked to fail with its fix removed.

Open steps come from two places. The code analysis returns them as `open` (prompt
version 2, `page-analysis.schema.json`), and `compile.merge.merge_open_steps` assesses
them like any fact. Steps read plainly in the code are trusted; deduced ones, and any
step naming a click that could change data (`is_risky_step`), become a question. The
developer's `--open`, saved in `routes.json`, always wins (`pipeline.write_skill`).

Open steps are a CSS selector or `text:Label`. One piece of JavaScript resolves them,
`inline_setter._STEP_TARGET`: the probe runs it through `build_open_script`, and the skill
runs it in `openForm`, which clicks only while the form's first steady field is hidden,
because an open step is often a toggle.

### Exports: one skill per page, or one bundled skill

Each product has two ways in, and `export` covers both shapes (`tests/test_export.py`):

| Layout | How | Who takes it |
| --- | --- | --- |
| one folder per page | `export` (the default) | a skills folder on the developer's machine |
| one bundled skill at the archive root |  `export --one-skill` | Claude's and ChatGPT's skill uploads |
| plugin, one folder per page | `export --plugin` | Claude Code |
| plugin, one bundled skill | `export-chatgpt` | ChatGPT and Codex, via the OpenAI portal |

A **skill upload takes one skill at a time**: its archive must hold exactly one
`SKILL.md`, the skill folder must be the archive's top level (`<skill-name>/SKILL.md`),
the folder name must equal the frontmatter `name`, and a plugin manifest makes it
refuse the archive. A **plugin** may hold many skills but needs its manifest and
`skills/<name>/`. Both products refuse a plain multi-page archive with "Zip must contain
exactly one SKILL.md file", which is why `cli.describe_export_use` warns after a plain
`export` of several pages, and why the README leads with `--one-skill`.

`generate/bundle.py` does the bundling, and `export._laid_out` chooses the layout:

- `build_entry_skill_md` writes the single `SKILL.md`: a table of forms (title, route,
  what is on the page, the file to read) and three rules for using it. It stays about
  25 lines, so a fill costs it plus one page file, whatever the page count.
- `build_page_files` moves each page's `SKILL.md` body to
  `references/<skill>/page.md` (frontmatter dropped), its `scripts/*` to
  `scripts/<skill>/*` and its other references to `references/<skill>/*`.
  `retarget_support_paths` rewrites the `scripts/…` and `references/…` paths inside
  every file, or a page's own text would point at files that are not there.
  `DROPPED_FOLDERS` leaves `evals/` out: developer test files are not skill content,
  and they were the only text naming Claude.
- `summarize_description` keeps the middle of a page description (what is on the page),
  because the table already has columns for the form and its route.
- `write_export(root_name=…)` names the archive's single folder after the skill, so
  `--out` cannot break the `<skill-name>/SKILL.md` rule.
- The bundled skill is checked with `check_skill_files` after bundling, so the
  frontmatter `name` matching the folder and the 500-line body limit still hold.
- `build_bundle_compatibility` writes the compatibility line from the pages' `app-url`,
  with the lead naming the AI the export is for: `BUNDLE_COMPATIBILITY_LEAD` (neutral)
  or `CHATGPT_COMPATIBILITY_LEAD`.

Both plugin manifests name the author `export.PLUGIN_AUTHOR` (`chapeee`), the
maintainer's decision in `docs/decisions.md`; no flag changes it. `check_chatgpt_names`
refuses an invalid name, or one too long for the `<plugin>:<skill>` identity (64
characters), before anything is written.

`--json`: `export` reports `path`, `skills`, `files`, `plugin` and `skill` (the bundled
name, empty without `--one-skill`); `export-chatgpt` the same but for its own schema.
`tests/test_bundle.py` covers the bundling, and `tests/test_export.py` checks each
layout, that only one `SKILL.md` is written when bundling, the forced archive root, the
Agent Plugins key and name rules, and that the icon is square and at least 48 px.
Nothing is uploaded in tests.

### Size budget

`validate.spec.check_skill_md` fails a body of 500 lines or more; the 5000-token budget
(`generate.skill_md.BODY_TOKEN_BUDGET`) is only a note (`validate.spec.find_size_notes`,
in `generate` results' `problems` and `validate`'s `notes`). `generate.folder.fit_skill_text`
first moves optional fields to `references/fields.md`, four at a time.

### Views: steps, tabs, dialogs

A page's hidden parts are `PageModel.views` (`model/page.py` `View`: name, `enter` clicks
from the part before, field `keys`, optional `leave` clicks). The analysis returns them as
`views` (prompt version 3); `compile.merge.merge_views` trusts views read in the code,
asks about deduced ones, and `find_view_candidates` stops at the first view with a risky
click (`is_risky_step`). With `--xy`, `pipeline.with_view_candidates` walks deduced views
too and `keep_proven_views` keeps those whose fields appeared.

One script does every walk. `inline_setter._VIEWS` (included only for pages with views)
reaches each part with `stepTarget`, waits for its fields, fills it, leaves it, and
reports `view` and `stopped` (with the page's `[role=alert]` and `field_error` texts).
`run(values, {"view": name})` stops in a part. The probe reaches each view with that same
call (`inline_setter.build_probe_call`), filling earlier parts with example values:
`probe.runner.plan_stages` plans one fresh load per view and per conditional field
(`choose_reveal_value`), and `measure_boxes` measures each stage. Landmarks for the
layout check come only from fields in no view. Tests: `test_inline_setter.py` and
`test_probe_runner.py` drive `tests/bench/site/wizard.html` (served at `/wizard`) in
Chromium with `tests/bench/wizard-analysis.json`; `test_merge.py`, `test_serialize.py`,
`test_pipeline.py` and `test_skill_md.py` cover the rest.

### Commands never ask

Commands are run by an AI agent, never by a person at a terminal, so no command may
prompt or wait for input. Replacing existing output is the one decision that stops
before any work; it takes a flag for the answer. Everything else the developer must do
never throws work away: the run does all it can from the code, then reports what is
needed in both the text and the `--json` output (`next`). The agent asks the developer
in chat and runs the command again.

`generate --overwrite` is the example. Without it, a skill whose folder already holds a
`SKILL.md` is left alone and reported with status `exists` (counted in `exists` in the
schema), before any analysis or probing runs. If nothing was left to generate,
`routes.json` is restored exactly, so a `--name` rename does not stick for a run that
wrote nothing.

### A run that stops says what comes next

When a route cannot finish, its result carries `next` (`schema/cli/generate.schema.json`)
and the exit code is `EXIT_NEEDS` (3). The pipeline only names the need
(`errors.Need` on `RouteOutcome.need`); `handoff.build_next_step` turns it into the
question and the commands, so the wording lives in one place.

| Need | Found by | `next` |
| --- | --- | --- |
| `analysis` | any `AnalysisError` except with `--analyzer replay` (`cli.finish_analysed`) | `analyse`: the agent writes `next.write` from `next.prompt` |
| `url`, `probe`, `chromium`, `server` | `probe.runner.find_xy_need`, before any work (`cli.find_xy_need_before_work`); x/y is then off for the run and the skill is written from the code (`cli.add_xy_need`) | `ask`; `run` is `doctor --fix` for Chromium |
| `login` | `measure_page_layout` when no field showed and the page has a password field or moved to another address (`Measurement.is_sign_in`) | `ask`, `run` = `login --url …`; the skill is still written |
| `open` | `measure_page_layout` when no field showed, after `pipeline.measure_page_model` tried the analysis's own open steps (`compile.merge.find_open_candidates`, never a risky one) | `ask`; `then` replaces `--open` with `--open 'text:<label>'` |
| `overwrite` | status `exists` | `ask`; `then` adds `--overwrite` |

`then` is the same command line again (`--overwrite` added when the skill was written,
`--url '<url>'` for the address). It costs little because each analysis is fingerprinted
(`pipeline.fingerprint_request`: the prompt plus every slice file's bytes) and reused
while that fingerprint holds. The fingerprint is the code only (slice files and
`PROMPT_VERSION`, not the route), so concrete pages built by one file share it.
`analysis.fingerprint` records what a saved analysis was made from; `request.fingerprint`
records the last request, so an analysis the agent wrote after it is accepted; an
analysis with no record is accepted when it is newer than every slice file. Recorded
analyses (`replay`) are never reused, so tests stay exact.

When `--xy` measures nothing, `pipeline.measure_page_model` first tries the analysis's
open steps, deduced ones included: fields appearing prove them, so they are kept and
their question dropped. When x/y could not be measured, `compile.layout.carry_layout`
keeps the last run's boxes for fields whose selector is unchanged; it only verifies, so
an outdated box can never aim a click. SKILL.md says how many fields were seen on the
live page (`skill_md.describe_checked_fields`).

`pipeline.write_skill` checks before it saves: when a check fails only the questions are
written, so `page.json` and the skill on disk keep matching.

### Logging

Use `logger = logging.getLogger(__name__)`, never `print` (only `cli.py` prints). The
console shows warnings (`-v` for info, `-vv` for debug); `.skillgendev/logs/` always gets
everything. Log what a developer needs to debug a run: inputs, counts, timings, external
calls and their errors. Never log secrets or personal data.

## Generated output rules

- With a measured layout, the skill also gets `references/layout.json`
  (`generate/layout_reference.py`): every measured box from `page.json`, in page and
  anchor-relative coordinates, with the same anchor and landmarks as the fill call's
  compact check (`inline_setter.build_geometry`, which holds landmarks only). It is
  read on demand, never on a normal fill. Tests: `test_layout_reference.py`.
- `SKILL.md` carries the inline setter (`generate/inline_setter.py`) with the page's
  selector map, so one `javascript_tool` call fills the page and nothing else is read
  first. It reports one status per key: `ok`, `partial`, `rejected`, `missing`,
  `escalate`, `unknown`.
- `fill.js` is the fallback, read only when a key comes back `escalate`. Both scripts
  are plain ES2019 with no dependencies and return compact JSON only. fill.js is
  bounded by `MAX_SCRIPT_BYTES`, not a line count.
- Both scripts write values through the prototype's setter (`put` in the setter,
  `setValue` in fill.js) and click boxes instead of setting `checked`: a
  framework-controlled input ignores a direct `el.value = …`, while the read-back still
  says `ok`. `test_setter_fills_inputs_a_framework_controls` (`-m browser`) rebuilds
  that trap and fails on a direct write.
- Every skill carries four fill methods, and `SKILL.md`'s "Choose how to fill"
  (`skill_md.render_choose_method`) tells the AI to use the first its browser tool
  supports: the JavaScript call, then `references/locators.md`
  (`generate/locators.py`: role, name, CSS and a Playwright-style action per field,
  grouped by view), then browser actions by label (`skill_md.render_browser_actions`,
  listing only the kinds of control the page has), then `references/manual-steps.md`
  (`generate/manual_steps.py`: numbered steps by labels and sections). The methods are
  named by ability, never by one product's tool names; locators are data, never code.
  Tests: `test_locators.py`, `test_manual_steps.py`, `test_skill_md.py`, and eval 4
  ("this browser cannot run JavaScript") in `test_evals.py`.
- Shipped data is read at the edge: `assets.read_fill_engine` and
  `assets.read_index_template`, never inside `generate/`, which stays pure.
- The layout check is optional and only exists with a probe. `probe/extract.js`
  measures each control's box from its final selector (the way the skill reads it back)
  at `runner.CAPTURE_VIEWPORT`; `compile/layout.py` keeps a box only when the probe's
  selector equals the field's; `inline_setter.choose_landmarks` picks up to eight, one
  per row; `build_geometry` writes them relative to the first. Tests:
  `tests/test_layout.py`, the layout cases in `tests/test_inline_setter.py`,
  `tests/test_serialize.py` and `tests/test_skill_md.py`. The JavaScript itself was
  checked live against the bench in each state (`match`, `resized`, `blocked`,
  `changed`); see `docs/decisions.md` for how, and rerun those cases after changing it.
- `SKILL.md` passes the [Agent Skills spec](https://agentskills.io/specification):
  the name is lowercase with single hyphens, at most 64 characters, and matches the
  folder; the description is quoted in YAML and under 300 characters; the body is
  under 500 lines.
- Text between `skillgendev:user:start` and `skillgendev:user:end` survives regeneration.

## Adding framework support (hint packs)

You do not need to touch Python to teach skillgendev a new router or validation
library. Add a YAML file:

- `hintpacks/routers/<name>.yml`: an ast-grep rule that matches route declarations,
  plus which metavariables hold the path and the component.
- `hintpacks/folders/<name>.yml`: a folder-routing convention (which folder, which
  file names are pages, how parameters are written, and with `requires_any` which
  files mark a project root, so apps nested in a monorepo are found:
  `routes/folders.py` `find_project_roots`).
- `hintpacks/validators/<name>.yml`: an ast-grep rule that finds field constraints.

A route the developer gives as one concrete page (`/users/7`) is linked to the
pattern found in the code (`/users/:id`) by `routes/paths.py` `match_route` and
`routes/merge.py` `find_pattern_files`: the pattern with the most fixed segments wins,
and a tie links nothing. `pipeline.ensure_route` also fills the code files of a route
already saved in `routes.json` without any, so its slice is never empty by accident.
Tests: `tests/test_folders.py`, `tests/test_paths.py`, `tests/test_route_merge.py`,
`tests/test_pipeline.py`.

ast-grep never searches dependency or build folders (`routes.folders.SKIPPED_FOLDERS`,
passed as `--globs` and filtered again in `astgrep.is_in_skipped_folder`), and a route
that is really a Windows path (Git Bash rewrites `/forms/x`) is refused by
`routes.paths.check_route_text`. When a component declares no symbol of its own name (a
`.vue` file), `graph.slice.find_imported_file_named` links it by file name.

Each hint pack needs a matching tiny example under `tests/fixtures/hintpacks/` and a
test. See `hintpacks/README.md`.

## Tests

- Every module has a test file. No network in tests.
- Browser tests (`-m browser`) only talk to a local server the test starts.
- Each example app in `tests/fixtures/` uses a different stack. A new stack is a
  welcome contribution: add the app, its recorded analysis, and its expected skills.
- Golden files: regenerate with `uv run pytest --update-golden` and review the diff.

## Testing in Claude and Cowork

`tests/bench/` is a one-page test bench: a form with every kind of widget skillgendev
supports (text, selects, radios, checkboxes, searchable dropdowns, dependent options,
conditional fields, a tree picker, chips, rich text, repeatable rows, file upload,
server-side errors), a tiny local server, the skill skillgendev generates for it, and a
list of test cases with expected results.

```bash
python3 tests/bench/serve.py               # http://localhost:8765, stdlib only
```

Then follow [`tests/bench/README.md`](tests/bench/README.md): install the bench skill
into Claude or Cowork, paste a test case's prompt, and run
`python3 tests/bench/check.py <case-id>` to compare what was submitted with what
was expected. Please include the results table in your pull request when you change
generated output.

## Commits and pull requests

- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
  `docs:`, `test:`, `refactor:`, `chore:`.
- Small commits, one change each.
- Never commit `.skillgendev/secrets/`, `.env` files or Playwright storage states.
- Record design decisions in `docs/decisions.md`.
- If something in the spec is unclear, open an issue and ask before building.

## Releasing

1. Raise `version` in `pyproject.toml` and `__version__` in `src/skillgen/__init__.py`.
2. Publish a GitHub release tagged `vX.Y.Z`. `.github/workflows/publish.yml` builds and
   uploads to PyPI with trusted publishing.
3. Update Homebrew: `python scripts/update-homebrew-formula.py` rewrites `url` and `sha256`
   in `packaging/homebrew/skillgendev.rb` from PyPI. Copy it to
   [chapeee/homebrew-tap](https://github.com/chapeee/homebrew-tap) as
   `Formula/skillgendev.rb` and push.

## Licence

By contributing you agree that your contribution is licensed under the Apache
License 2.0 (see `LICENSE`).
