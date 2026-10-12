# CLAUDE.md — project rules for skillgendev

These rules apply in every session. When a rule and a request conflict, ask first.
The source of truth for *what* we build is `docs/spec.md` (Code-to-Skill Compiler,
Final Spec v2). The overrides in "Project decisions" below win over the spec.

## What we are building

A framework- and domain-agnostic compiler. It reads an app's code route by route
and writes one build-ready Agent Skills folder (`SKILL.md` + `scripts/fill.js`) per
page, so Claude or Cowork can fill that page's form with few tokens.

## Project decisions (override the spec)

- **No MCP anywhere.** The library does not depend on, install, or mention MCP servers.
  Generated skills never mention them either.
- **Skills are for any AI that accepts Agent Skills**: Claude, Cowork, or another.
  They must work with that AI's built-in browser and nothing installed, so never rely on
  one product's tool names.
- **Every skillgendev command is run by an AI agent** (Claude Code through `/skillgendev`, or
  another), never by a person at a terminal. So no command may prompt or wait for
  input. Replacing existing output is the one decision that stops a command before any
  work (`generate --overwrite`). Anything else the developer must do (an address, a
  sign-in, a download, the button that opens a form) never throws work away: the run
  does all it can from the code, then says what is needed (`next` in `--json`). The
  agent asks the developer in chat and runs it again; analysis is reused while the code
  is unchanged. Only the exported skills leave the agent: they go to whichever AI will
  fill the page.
- **Code-only generation is the default.** The Playwright probe is an optional extra
  (`pip install skillgendev[probe]`) and runs only with `generate --xy` (or `--url`, which
  implies it). It only adds x/y: a skill's fields always come from the code, so `--xy`
  is never worse than a normal run.
- **Public name is `skillgendev`** (PyPI package and command; `skillgen` was taken on
  PyPI). It lives in exactly one constant (`skillgen.TOOL_NAME`) plus the `[project]`
  name and script entry in `pyproject.toml`. The import package and folder stay
  `skillgen` (`src/skillgen/`); do not rename files or folders. Every other place
  (workspace folder `.skillgendev/`, schema ids, markers, metadata) derives from the
  constant. Never hard-code the name anywhere else.

## For any project, any user

- skillgendev is a general tool: anyone runs it on their own app. Nothing may assume our
  apps, our names or our hosts.
- The user always chooses the skill names. Every `generate` accepts `--name`:
  with `--route` it is the exact skill name; with `--all` it is the prefix for every
  skill (`--name acme` → `acme-<route-slug>`). Names in `.skillgendev/routes.json` can be
  edited per route. Without `--name`, the prefix comes from `config.json` `app_name`,
  then the repository folder name. Every chosen name is checked against the Agent
  Skills rules and rejected with a clear message when it does not pass.

## Documentation for every command

- Every CLI command and flag is documented in two places, in the same change that adds it:
  `README.md` (for people using skillgendev: what it does and an example) and
  `CONTRIBUTING.md` (for contributors and maintainers: where it lives, its `--json`
  schema, how it is tested). `tests/test_docs.py` fails when a command is missing.

## Language and tooling

- Python 3.10+. Code must run on 3.10 (no `match` on 3.11-only features, no
  `typing.Self`, no `ExceptionGroup`).
- `uv` for environments: `uv sync --all-extras`, `uv run pytest`.
- `ruff` for lint and format: `uv run ruff check .` and `uv run ruff format .`.
- `mypy` in strict mode: `uv run mypy`.
- `pytest` for tests: `uv run pytest`. Browser tests: `uv run pytest -m browser`.
- Before every commit run all four: `ruff check`, `ruff format --check`, `mypy`,
  `pytest`. Do not commit red.

## Layout

```text
src/skillgen/
  __init__.py      # TOOL_NAME, __version__
  cli.py           # the only place allowed to print
  workspace.py     # .skillgendev/ layout, reading and writing its files
  config.py        # config.json
  pipeline.py      # runs the per-route steps; file and subprocess access at the edge
  handoff.py       # the next step a stopped run hands to the agent or the developer
  assets.py        # finds shipped data (hintpacks/, claude/) in a wheel or a checkout
  export.py        # folder, zip or plugin export with MANIFEST.sha256 and the secret scan
  logs.py          # run logs: console by -v, full debug log in .skillgendev/logs/
  errors.py        # every custom exception
  graph/           # Graphify adapter, page slice, change impact
  routes/          # route probes, merge into routes.json, skill names
  probe/           # optional: Playwright fields, behaviour diff, submit interception, crawl
  analyze/         # prompts, page-analysis.schema.json, headless runner
  model/           # page.json schema, facts, confidence
  compile/         # merge probe, code and analysis facts into page.json; compile rules into checks
  generate/        # SKILL.md renderer, fill_engine.js, references, evals, index page
  validate/        # spec checks, model checks, secret and personal-data scan
  verify/          # with-skill vs without-skill runs
  drift/           # check, semantic diff
  schema/          # JSON schemas: page.json and every CLI --json output
claude/            # /skillgendev command, route-analyzer agent, driver skill
hintpacks/         # framework knowledge as YAML data: routers/, validators/, folders/
tests/             # unit tests, tests/fixtures/ (example apps), tests/bench/ (test page)
docs/              # spec.md, decisions.md
scripts/           # install-local.ps1 / install-local.sh: global editable install for testing
```

Import boundaries (checked by `tests/test_boundaries.py`):

- `graphify` is imported only inside `src/skillgen/graph/`.
- `playwright` is imported only inside `src/skillgen/probe/`, and only lazily, so
  the core works without the `probe` extra.
- No module outside `cli.py` calls `print`.

## Naming

- Modules: lowercase nouns (`slice.py`, `confidence.py`).
- Functions: snake_case starting with a verb (`find_routes`, `build_page_model`,
  `write_skill`).
- Classes: PascalCase nouns (`PageModel`, `FieldSpec`). Constants: `UPPER_SNAKE`.
- Booleans: `is_`, `has_`, `should_` prefixes (`is_required`, `has_probe`).
- No abbreviations except `url`, `id`, `json`, `html`, `api`. `config` is allowed
  only as the module name the spec gives; in code write `settings`, never `cfg`,
  `btn`, `el`, `opts`, `idx`.
- Test files: `test_<module>.py`. Test names: `test_<function>_<behaviour>`
  (`test_combine_confidence_caps_disagreeing_sources`).

## Functions

- One job each, about 40 lines maximum. Split when longer.
- Type hints on every argument and return value. No `Any` without a comment saying why.
- `model/`, `compile/` and `generate/` are pure: no file, network, subprocess, clock
  or environment access. They take data and return data. File and network access
  happen only at the edges (`workspace.py`, `cli.py`, `graph/`, `routes/` scanners,
  `analyze/runner.py`, `probe/`, `verify/`).
- Prefer frozen dataclasses for data. No global mutable state.

## Comments and docstrings

- Google-style docstring on every public function and class: what it does,
  `Args:`, `Returns:`, `Raises:` (omit a section only when it is empty).
- Inline comments explain *why*, never *what*.
- No commented-out code.
- TODOs carry an issue number: `# TODO(#12): support multi-route wizards`.

## Errors and output

- Custom exceptions live in `errors.py` and inherit from `SkillgenError`.
- Never a bare `except:` and never `except Exception:` without re-raising or a
  comment saying why it is safe.
- Use the `logging` module (`logger = logging.getLogger(__name__)`), never `print`,
  except in `cli.py`.
- Every CLI command supports `--json`. Its output is validated against
  `src/skillgen/schema/cli/<command>.schema.json` before it is printed, and a test
  checks every command has a schema.

## Data

- Every fact records its source and its confidence. Sources: `RUNTIME_PROBED`,
  `EXTRACTED`, `CLAUDE_INFERRED`, `DEVELOPER_CONFIRMED`, `USER_DEFINED`.
- Confidence follows the spec: agreeing sources combine as `1 − (1 − a)(1 − b)`,
  disagreeing sources cap at 0.5 and raise a question, facts below 0.7 stay out of
  the skill.
- Evidence (file paths, line numbers, probe captures) stays in `.skillgendev/` and never
  reaches `SKILL.md`, `fill.js`, or anything `export` writes.
- No secrets or real personal data in fixtures, output or logs. Use synthetic values
  (`example.com`, `555-0100` style numbers, obviously fake names).

## Framework-agnostic rule

- No framework-specific code in the core. No `if framework == "vue"`, no import of a
  framework's parser, no hard-coded router names.
- Framework knowledge lives only in `hintpacks/` as YAML data (ast-grep rules and
  folder-routing conventions). Deleting `hintpacks/` must leave a working tool.
- Same for domains: no business vocabulary in code or templates.

## Fill scripts

Two scripts, both plain ES2019 with no dependencies: no `?.`, `??`, `||=`, numeric
separators, `globalThis`, `replaceAll`, `.at()`, `Promise.allSettled`, classes with
private fields. Both return compact JSON only; page text in results is truncated and
treated as data.

- **The inline setter** (`generate/inline_setter.py`) is the fast path. `SKILL.md`
  carries it in full with the page's selector map, so one `javascript_tool` call
  fills the page and nothing else is read first. It reports one status per key and
  says `escalate` for anything it cannot do.
- **fill.js** (`generate/fill_engine.js` plus a generated field map) is the fallback,
  read only when the setter escalates. The engine is the same in every skill; only
  the field map at the top differs.
- Size is measured in bytes, not lines: `MAX_SCRIPT_BYTES` binds fill.js, and the
  field map is written one entry per line. Never satisfy a size rule by making lines
  longer.
- **The layout check is optional.** With a probe-measured `layout`, the setter checks
  the live page against landmark fields and fills only on `match` or `resized`; a
  failed check writes nothing. Without a layout it fills as before. Stored positions
  only ever verify; anything clicked is measured live with `locate(key)`. The check
  must never stop Claude inspecting the page and filling with `{"verify": false}`.
- Each part of the setter costs a reader on every fill, so include it only when the
  page needs it (`render_engine(has_checks, has_manual)`).

## Generated SKILL.md

- Must pass the Agent Skills spec: `name` is lowercase letters, digits and single
  hyphens, at most 64 characters, identical to its folder name.
- `description` is always quoted in YAML and under 300 characters.
- Body under 500 lines (and about 5k tokens).
- No evidence, file paths, class names or source code.
- Text between `skillgendev:user:start` and `skillgendev:user:end` markers survives
  regeneration untouched.

## Tests

- Every module gets tests (`tests/test_<module>.py`).
- No network in tests. Browser tests talk only to a local server started by the test
  and are marked `@pytest.mark.browser`; they skip when Playwright is not installed.
- Each example app in `tests/fixtures/` uses a different stack.
- `tests/bench/` holds the one-page test bench for checking skills end to end in
  Claude and Cowork. Keep its skill regenerated (`test_bench.py` checks it).
- Golden files are regenerated with `uv run pytest --update-golden`, and the diff is
  reviewed before committing.

## Git

- Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
- Small commits, one change each.
- Never commit `.skillgendev/secrets/`, `.env`, or Playwright storage-state files.

## Working style

- When the spec is unclear, ask instead of guessing. If the user is away, choose the
  smallest reversible option, record it in `docs/decisions.md` under
  "Open questions", and carry on.
- Keep a decision log in `docs/decisions.md`: date, decision, why, alternatives.
