# Decision log

Newest first. Each entry: date, decision, why, alternatives considered.
Open questions for the maintainer are at the top; answered ones move into the log.

## Open questions

These came up while the maintainer was away. Each was settled with the smallest
reversible choice; tell me if you want another.

1. **Descriptive facts below 0.7.** The spec says facts under 0.7 wait for the
   developer. Applied literally, every inferred field *meaning* (Claude's reading,
   0.60) would become a question, which breaks the "under 10 questions per 50-field
   page" goal. Current choice: facts that change how a field is filled (required,
   options, conditions, rules, selectors, strategy) below 0.7 become questions;
   descriptive text below 0.7 is dropped from `SKILL.md` without a question.
2. **Host check in `fill.js`.** `fill.js` refuses to run when `location.hostname`
   differs from the skill's `app-url` hostname. It compares hostnames, not ports, so
   the same skill works on a dev server whose port changes. OK?
3. **Folder routing as data.** The spec lists "folder-based routing" as a generic
   route probe, but the details (`pages/`, `app/…/page.tsx`, `+page.svelte`,
   `[id]` vs `:id`) are framework knowledge. Current choice: they live in
   `hintpacks/folders/*.yml` as data, read by one generic scanner.
4. **`verify` (with vs without skill).** The spec runs headless Claude Code with a
   browser tool. Headless `claude -p` has no built-in browser without an MCP server,
   which our rules forbid. Current choice: no `verify` command yet; each skill ships
   `evals/evals.json` and the bench has manual Claude/Cowork cases. Options: run evals
   by hand in Claude/Cowork and record results, or allow an MCP browser for the
   developer's machine only (never in skills).
5. **Rename.** Spec section 16 recommends "Formcast". The repository is called
   `skillprinter`, and the spec lists "Skillprint" as a name to avoid because a
   company uses it. Still `skillgendev` until you decide.

## 2026-10-08 — headless Claude Code on Windows

**Decision.** Run the path `shutil.which` resolves, send the prompt on standard input
(UTF-8), and when that path is a `.cmd`/`.bat` shim put the answer schema in the
prompt instead of `--json-schema`.
**Why.** Windows starts only `.exe` files by bare name, so `claude` installed by npm
(`claude.cmd`) failed with `FileNotFoundError`. A shim also runs its arguments
through cmd.exe, which cuts the prompt at newlines and mangles the schema's quotes
and carets. The answer is checked against the schema afterwards either way.
**Alternatives.** Escaping arguments for cmd.exe (fragile, double escaping for npm
shims); finding the `node` script behind the shim (depends on npm's shim layout).

## 2026-10-08 — routes for every stack: hint packs, Graphify route nodes, Claude reads the graph

**Finding.** Tested on Rails, Spring, ASP.NET, Phoenix and Laravel samples: Graphify
extracts routes only for Razor `@page` and Dart, and links router files to controllers in
some stacks (Laravel, Spring) but not others (Phoenix, ASP.NET MVC, Rails views).
**Decision.**
- Graphify's route nodes are now a route source (`graph:graphify`).
- New router packs: Rails, Spring MVC, ASP.NET Core attributes and Phoenix. Laravel now
  captures the controller. Packs can reshape captured targets (`component_match`,
  `component_format`), and symbols match by their last dotted segment.
- **Claude reads the graph** (the maintainer's idea): `graph/hubs.py` ranks likely router
  files by fan-out, generic name hints and Graphify route nodes. Claude Code reads them
  with read-only tools and returns routes (`route-listing.schema.json`). It runs
  automatically when nothing else finds a route, or with `routes --ask-claude`. It was
  tried live: it expanded Rails `resources` and found Go `net/http` routes with no pack.

## 2026-10-08 — run logs, local install scripts, docs for every command

- Every command writes a debug log to `.skillgendev/logs/` (newest 30 kept, gitignored,
  never exported). `skillgendev logs` shows it, and errors print its path.
- `scripts/install-local.ps1` and `.sh` install the clone globally in editable mode,
  like `npm link`. Tested with PowerShell 7 and bash.
- Every command and flag must be in the README (users) and CONTRIBUTING (maintainers);
  `tests/test_docs.py` enforces it.

## 2026-10-08 — fixes from a first real install and a live Claude Code run

- skillgendev was installed from a clone (`uv tool install --editable ".[astgrep,probe]"`)
  until it was published. Superseded on 2026-10-12: it is on PyPI as `skillgendev`, and the
  README says `uv tool install "skillgendev[probe]"`.
- `ast-grep` is looked up next to the running Python first: tool installs (uv, pipx)
  keep the extra's binary inside skillgendev's environment, off PATH.
- `skillgendev doctor --fix` downloads Chromium with `python -m playwright` for the same
  reason.
- `claude --json-schema` rejects the draft 2020-12 `$schema` key, so it is dropped from
  the schema passed to Claude Code.
- The submit selector is always treated as read from markup; the analysis's `inferred`
  flag on `submit` now covers only the success signal. Success URLs must be plain text;
  regular expressions are dropped because fill.js matches text.

## 2026-10-08 — index, drift and export

- `skills-index.html` is one self-contained file; the graph layout is computed in
  Python and drawn on a canvas, so it works offline and from a zip. The template lives in
  `generate/index_template.html`.
- `check` compares changed files (git diff plus untracked, minus skillgendev's own output)
  with saved page slices, widened by two reverse hops in the code graph. It exits 1 when
  skills are stale, so it can gate CI; `--regenerate` rebuilds them.
- Regeneration writes `pages/<skill>/changes.json` (a semantic diff); the index shows a
  "changed" badge.
- `export` refuses any skill that fails its checks or the secret scan, and writes
  `MANIFEST.sha256`. `--plugin` adds `.claude-plugin/plugin.json`.
- `generate --route /x` for a route not yet in `routes.json` now runs the route probes
  first, so the route gets its entry files and a real slice.

## 2026-10-08 — decisions made while building the pipeline

- **All JSON schemas live in `schema/`**, including `page-analysis.schema.json` (the spec
  puts it in `analyze/`). One loader validates every document.
- **`pipeline.py` orchestrates** the per-route steps; `cli.py` only parses arguments and
  prints. Analysis runs in parallel; merging and writing run one route at a time so
  `routes.json` and `questions.json` are never written concurrently.
- **Missing `required` attributes are not evidence.** Apps often validate in script, so
  the probe only says a field is optional when the empty-form submit ran and showed no
  error for it. Tree pickers' top-level items are not compared with full paths.
- **Repeated rows are matched by group, never by probe**, because the probe sees row 0's
  selector (`items[0][name]`), which would break filling a second row.
- **Passwords and secrets use the `steps` strategy**: the user types them; skills never
  ask for or fill a secret. Required manual fields are reported under `manual`.
- **fill.js engine size.** The engine is about 200 lines and roughly 4k tokens, more than
  the spec's 1.5k estimate. Claude sends it once per page; later calls are only
  `__fill({...})`. A minified build is a later option.
- **Slices expand only from the page's own entry file.** The router file that declares a
  route is included as context but not followed, so sibling pages stay out. Package
  manifests are dropped from slices.
- **The bench page model is produced by skillgendev itself**: `tests/bench/analysis.json`
  (what Claude would return) plus `tests/bench/probe.json` (a real probe capture) are
  merged into `page.json`, from which the bench skill is generated. Golden tests keep
  all three in step.
- **The probe never writes data**: every non-GET request is aborted. The browser test
  asserts the bench server received zero submissions.

## 2026-10-08 — users choose skill names (`--name`)

**Decision.** `skillgendev generate` takes `--name`. With `--route` it is the exact skill
name; with `--all` it is the prefix for every skill (`acme` → `acme-developer-kyc`).
Per-route names can also be edited in `routes.json`. Default prefix: `config.json`
`app_name`, then the repository folder name.
**Why.** The maintainer: skillgendev is for any project and anyone; users must be able to
name their own skills. **Alternatives.** Separate `--prefix` flag (one flag is simpler
to remember; its meaning follows from one route vs all).

## 2026-10-08 — `compile/` package for merging

**Decision.** Add `src/skillgen/compile/` beside the spec's packages. It holds the
deterministic merge (probe facts + code facts + Claude's analysis → `page.json`,
conflicts → `questions.json`) and the compilation of rules into `fill.js` checks.
**Why.** The project rules name `compile/` as a pure package; the spec's section 13
puts merge in `model/`. Keeping `model/` for data shapes and `compile/` for the
transformation keeps both small. **Alternatives.** Merge inside `model/`.

## 2026-10-08 — hint packs and Claude assets ship inside the wheel

**Decision.** `hintpacks/` and `claude/` stay at the repository root (spec section 13)
and are force-included into the wheel under `skillgendev/_data/`.
**Why.** `skillgendev install` and route discovery must work from `uv tool install`.
**Alternatives.** Move both under `src/skillgen/` (breaks the spec layout).

## 2026-10-08 — PyYAML is a core dependency

**Decision.** Add `PyYAML` to the core dependencies.
**Why.** Validating `SKILL.md` frontmatter and reading hint packs both need a YAML
parser; writing our own is a risk for a spec check. **Alternatives.** A minimal
frontmatter parser (fragile on quoting, which the spec cares about).

## 2026-10-08 — the analyzer is pluggable; interactive mode needs no subprocess

**Decision.** The analysis step has three runners behind one interface:
`claude -p --json-schema` (batch), a file written by Claude Code itself in
interactive `/skillgendev` mode (`skillgendev prepare` prints the prompt and schema,
Claude writes `analysis.json`, `skillgendev generate` reads it), and a replay runner
that reads recorded analyses (tests and fixtures).
**Why.** Tests must not call the network, and inside Claude Code the CLI should not
start a second Claude. **Alternatives.** Subprocess only.

## 2026-10-08 — project overrides adopted from the maintainer

- No MCP anywhere; skills target Claude and Cowork with the built-in browser.
- Code-only generation is the default; the Playwright probe is the `probe` extra and
  runs only when `--url` (or `config.json` `app_url` with `probe: true`) is given.
- Working name `skillgendev`, held in `skillgen.TOOL_NAME` and the package name.

## 2026-10-08 — Graphify confirmed as the code-graph layer

**Decision.** Use `graphifyy` (0.9.80 checked) `graphify.extract.collect_files` and
`graphify.extract.extract`, collapsed to a file-level graph in `graph/`.
**Why.** Checked on a small React + Vue sample: it emits `imports_from`, `imports`,
`calls` and `dynamic_import` edges with `source_file` on every node, which is what a
page slice needs. Vue templates yield no symbols (as the spec says), but the
`<script>` imports are still extracted.

## 2026-10-08 — SKILL.md carries an inline setter; fill.js becomes the fallback

**Decision.** `SKILL.md` carries a compact setter (`generate/inline_setter.py`) with
the page's selector map, and the fill step is one `javascript_tool` call. The full
engine stays at `scripts/fill.js`, read only when a key comes back `escalate`. The
generated skill also states plainly that the page must not be read, listed or
screenshotted before filling.

**Why.** Pointing at `scripts/fill.js` cost a reader the engine twice: once reading
the file, once passing its text to the browser. Measured on the bench skill, one fill
went from 10,869 to 3,877 tokens, a 64% cut. The old shape also made a skill cost
*more* than no skill, because nothing stopped the page being read as well.

**Alternatives.** Minifying the engine: dropped, because prompt caching already makes
resident context cheap after the first turn, so the saving was far smaller than it
looked. Precomputed click coordinates: rejected — the browser pane reported a 0x0
viewport, it clears an emulated size when a turn ends, conditional fields reflow the
page, and a stale coordinate fails silently by typing into the wrong field. A test of
normalise-then-rescale was off by 150px at 600x900 on an element that had not moved at
all; CSS layout is not proportional to the viewport. Addressing fields by
accessibility-tree name through `find`: rejected — 7 of the bench's 21 fields have no
unique accessible name (two comboboxes both named "Choose…", two checkboxes both named
"on", three unnamed textboxes). Selectors are the only precomputable address that is
both exact and viewport-independent, and `javascript_tool` accepts them.

## 2026-10-08 — the generated script's budget is bytes, not lines

**Decision.** `MAX_SCRIPT_BYTES` replaces `MAX_SCRIPT_LINES`, and the field map is
written one entry per line.

**Why.** Bytes are what a reader pays for. The old cap was met by packing several
field entries onto one line, which made lines longer without making the file cheaper,
and the engine's 202 lines left only about 46 for the field map.

**Alternatives.** Keeping both caps: rejected as two numbers for one property.

## 2026-10-08 — pure packages are checked for every kind of file access

**Decision.** `test_pure_packages_do_no_io` matches `open`, `read_text`, `read_bytes`,
`write_text`, `write_bytes`, `Path(`, `getenv`, `resources.files` and `os.environ`,
each as a whole word. Reading shipped data moved to `assets.py`
(`read_fill_engine`, `read_index_template`) and the text is passed in as data.

**Why.** The check tested only for the literal `open(`, so two real violations sat in
`generate/` unnoticed: `fill_script.load_engine` and `index_page.render_index_html`
both read shipped files through `importlib.resources`.

**Alternatives.** An AST walk: more precise, but the word-boundary scan found both
violations and stays readable.

## 2026-10-08 — an optional layout check verifies the page before a skill trusts it

**Decision.** When the probe ran, the page model carries a `layout`: the viewport it was
measured at and each visible field's box in document coordinates. The inline setter
then checks the live page against up to eight *landmark* fields before it writes
anything, and reports `match`, `resized`, `blocked` or `changed`. It fills only on
`match` or `resized`. A skill generated without the probe has no layout and fills
exactly as before; the check is never required.

The parts that make it safe:

- **Stored positions verify; they are never clicked.** Anything Claude must click is
  measured on the screen at hand with `locate(key)`, which scrolls the field into view
  and returns its centre. A stale coordinate can therefore never aim a click.
- **Offsets are measured from the first landmark**, not from the page, so a banner
  above the form, centring on a wider screen and the scroll position all cancel out.
  Tested: a 140px banner pushing the whole form down still reads `match`.
- **Width decides the screen.** Within 8px of the measured width, positions and heights
  are compared with tolerances that grow down the page (font differences accumulate).
  On any other width only structure is compared — present, visible, in order — because
  a responsive layout legitimately moves things. Tested at 1000x760, 760x820 and 640x900.
- **One landmark per row**, so order survives two columns collapsing into one.
- **`elementFromPoint` finds what covers the form.** A dialog over the form reads
  `blocked` even though every field is exactly where it should be (score 1.0); a sticky
  header over a single field is reported but does not block, as one covered field of
  several in view is not a majority.
- **A failed check writes nothing.** Tested by removing two fields: `changed`, score
  0.38, and the form was left empty.
- **The setter stays loaded** under `window["__<tool>"][<skill>]`, so filling after an
  inspection, or adding values the user gave later, costs about 53 tokens. The original
  `fill.js` had this (`__fill`); the first inline setter lost it by resending its whole
  block (about 1,169 tokens), and this restores it.

**Departure from the request.** The request said to take a screenshot first and compare
it with the stored geometry. The check instead measures the page with
`getBoundingClientRect` and `innerWidth`, which return the layout engine's exact
numbers, and a screenshot is taken only on `blocked` or `changed`. A screenshot costs
about 1,200 tokens and asks Claude to estimate pixel positions from an image. Restoring
a screenshot first is a one-line change in `skill_md.render_fast_path`.

**Cost.** Measured on the bench skill, one fill: Phase 1 3,877 tokens; with the cache
and `locate` but no layout 4,453; with the layout check 5,707. The check is a
reliability layer, not a saving on a single fill. What it buys is that a changed or
covered page is never written to.

**How the bench was measured.** Playwright is not installed in this environment, so
the bench's boxes were captured by running the real `probe/extract.js` in Chromium at
the capture viewport (1280x900) and written into `tests/bench/probe.json` by selector.
`page.json` is then compiled from it by the normal pipeline. The Python Playwright
wiring in `probe/runner.py` (fixed viewport, on-load boxes only) is covered only by the
browser tests, which skip without the `probe` extra.

**Alternatives.** Normalising positions to the viewport and rescaling: rejected, off
by 150px at 600x900 on an element that had not moved. Comparing every field instead of
landmarks: more bytes on every fill for little more certainty. A screenshot-first
comparison: see above.

## 2026-10-09 — commands never ask; an existing skill needs --overwrite

**Decision.** `generate` leaves a skill whose folder already holds a `SKILL.md` exactly as
it is, and reports it with status `exists`, unless `--overwrite` is given. The check runs
before any analysis or probing, so declining costs nothing. If a run ends up writing
nothing, `routes.json` is restored, so a `--name` rename does not stick. `prepare`
reports `skill_exists`, so an agent can ask before it spends anything on analysis. The
driver instructions tell the agent to ask the developer in chat and to run again with
`--overwrite` on a yes, and to pass `--overwrite` when regenerating after answering
open questions.

**Why.** The maintainer asked for a confirmation before a skill is recreated. skillgendev is
always run by an AI agent, never at a terminal, so the command cannot ask: there is no
terminal to answer from, and a prompt would fail at once or hang. The question has to
be the agent's, and the command's job is to stop safely and say what it needs.

**Alternatives.** A `[y/N]` prompt when stdin is a terminal: dead code under an agent, and a
hang if a terminal were ever attached. Reusing `--force`: it already means "retry routes
marked as having no form". Refusing only in `--json` mode: the agent also runs without
`--json`, and the text output now says the same thing.

## 2026-10-09 — two modes: normal (code only) and `--xy` (normal plus x/y)

**Decision.** `generate` builds every skill from the code alone. `--xy` (or `--url`,
which implies it) also opens the page on the dev copy, clicks the route's open steps,
measures where each field sits, and attaches that layout to the code-built skill,
matched by selector. The probe no longer feeds facts into the merge, so `--xy` can only
add x/y: it never removes a field, changes one, or adds a question. Without `--xy`
nothing is measured and no saved capture is read. `probe` in `config.json` no longer
opens a browser by itself; the command decides. `skillgendev install` downloads Chromium
when the probe extra is installed (`--no-chromium` to skip).

Open steps (`generate --route … --open STEP`, saved in `routes.json` as `open`) are what
to click before a form shows: a CSS selector, or `text:Label`. The probe makes those
clicks before it measures, and the skill makes them before it fills, only while the
form's first steady field is hidden, because such a button is usually a toggle.

**Why.** On a page whose form sits behind a closed panel the old probe saw none of the
code's 16 fields, decided they were "not on the page", dropped them and failed the
build. Worse, `--code-only` still read that saved capture, so the next code-only run
failed too, for reasons that looked unrelated. The maintainer asked for two simple
modes chosen in the command, with x/y never making a skill worse.

Measuring is by the skill's own selectors (`probe/measure.js`), after the page is built
from the code. The first version matched what the probe found to the skill's fields by
selector, and on a real page measured 34 controls but matched none: the probe named them
`input` and `select`, while the skill's selectors came from the code. Tested on that page
afterwards: x/y for all 13 measurable fields, and the shipped skill opened the panel,
read `match` (score 1.0) and filled, both with the panel closed and already open.

**Alternatives.** Keeping the probe's fact checks in the merge and ignoring a probe that
matched under half the fields: still lets a partial view drop fields. A separate opt-in
for fact checking: possible later; `skillgendev probe` still shows what the probe finds.
A per-route "skip the probe" switch: treats the symptom, not the hidden form.

## 2026-10-09 — the code analysis says how a hidden form opens

**Decision.** The page analysis returns `open`: what to click, in order, before the form
shows (prompt version 2). `merge_open_steps` treats it as a fact: steps read plainly in
the code are trusted, deduced ones become a question, and a step naming a click that
could change data or leave the page (`is_risky_step`: save, submit, delete, remove,
publish, sign out) is never trusted without the developer's yes. The developer's
`--open` always wins. `--xy` makes the resolved clicks in Chromium before measuring and
warns when they reveal nothing; the skill makes the same clicks only while the form is
closed.

**Why.** On the real state-location page the analysis had already found the button,
`button[title="Page settings"]`, but only as a sentence in a gotcha, so the developer had
to type `--open`. Taking that same selector from the analysis and clicking it in Chromium
put 13 of 13 fields on screen. The maintainer asked for the code graph and Claude's
reading of the code to drive this, so nothing is rediscovered by hand.

**Alternatives.** Having Claude write page-specific JavaScript to open each form: not
repeatable, not testable, and a wrong guess could press a destructive button. Claude
names what to click; one shared, tested routine does the clicking in both the probe and
the skill. Coordinates stay a fallback: they verify the page, and `locate` gives live
positions for fields done by hand.

## 2026-10-09 — audit fixes: monorepo routes, concrete routes, line endings

**Decision.** Six fixes from an audit of what was promised against what the code did:

1. Folder packs apply at every project root marked by `requires_any`, at any depth,
   not only at the repository root (`find_project_roots`). Next.js and SvelteKit packs
   now list their config files and `package.json`.
2. A route given as one concrete page (`/cms/locations/states/134`) is linked to the
   pattern found in the code (`/cms/locations/:level/:id`). The most fixed segments
   wins, and a tie links nothing. A saved route without code files gets them filled
   in `routes.json`.
3. Workspace and export files are written with LF line endings, so `MANIFEST.sha256`
   matches the bytes on Windows too.
4. Gotchas deduced by the analysis become questions instead of being dropped silently.
5. Regenerating without `--xy` reports that the saved x/y was dropped.
6. The probe makes the route's open clicks on every page load, not only when
   measuring, and `merge_routes` keeps saved `open_steps`.

**Why.** On the real farmland monorepo, route discovery found 0 pages (the apps sit
two folders down). After fix 1 it found 137, and the backend's `app/` folder gave
none. The state-location skill was analysed from an empty slice because its concrete
route matched nothing. After fix 2 the slice has 11 files, `LocationForm.tsx` among
them. Graphify itself was checked as well: node IDs do not collide in 0.9.80.

**Alternatives.** Scanning every folder named `app` or `pages` anywhere: it picked up
`components/pages` and a Laravel `app/`. Choosing between equally good patterns by
file order: a silent wrong guess is worse than an empty slice the developer can see.

**Consequence.** A Next.js or SvelteKit project is now found only where its folder holds
`package.json` or its config file. Every real project has one; a bare `app/` folder with no
`package.json` (seen only in one test) is no longer scanned. Loosening this to "also the
repository root" was rejected because it brings back the false `app/` matches.

**Known limit.** Two apps in one repository that both have a home page share the
route `/`. Their files are merged into one entry; give the route a different skill per
app by hand.


## 2026-10-09 — a run that stops says what comes next, and the next run continues

**Decision.** When `generate` cannot finish a route, the result says why and what to do
next (`next` in `--json`, exit code 3), and the agent running skillgendev does it or asks
the developer, then runs the `then` command:

- Headless analysis failing (not signed in, usage limit, not installed, off-schema) is
  handed to the agent: it reads the prompt and writes the analysis itself.
- `--xy` checks before any work that it has an address, the probe extra, Chromium and a
  dev server that answers; each missing one is a question, never a half-finished run.
- A page that shows a sign-in page instead of the form still gets its skill from the
  code; the developer is offered `skillgendev login`, which opens a window they sign in to.
- Every analysis is fingerprinted (prompt plus slice files) and reused while it holds,
  so continuing costs nothing and an agent's own analysis is picked up without
  `--analyzer file`.
- `write_skill` saves `page.json`, evidence and the skill only after every check passes.

**Why.** On the farmland project a `--xy` run with no address warned and carried on for
two minutes, then failed: the inner `claude -p` was signed out, and the reason was buried
in raw JSON. The developer then had to switch analyzers and rerun by hand. The
maintainer asked for the workflow to handle what it can, ask only for what a person
must do, and continue where it stopped, without changing the approach (code first,
Graphify slice, Claude returns data, x/y only verifies).

**Alternatives.** Detecting "running inside Claude Code" from environment variables and
skipping `claude -p`: tied to one product, and the agent may be another. Asking with a
prompt in the terminal: commands never ask. Reusing `analysis.json` by date alone: an old
analysis would survive code changes.

## 2026-10-09 — x/y problems never cost the code skill; recover before asking

**Decision.** Only replacing an existing skill stops a run before any work. A missing
address, server, Chromium or sign-in now writes the full code-built skill first and then
asks, and the analysis is reused on the next run. When no field shows, `--xy` tries the
analysis's own open steps (never a risky one); fields appearing prove them. Unmeasured
runs keep the last x/y for fields whose selector is unchanged. The analysis fingerprint
is the code only, and an unrecorded analysis newer than its code is reused. ast-grep is
a core dependency. SKILL.md says how many fields were seen on the live page.

**Why.** The maintainer's farmland runs kept stopping on recoverable problems: a closed
"Page settings" panel the code already named, a reused analysis rejected because the
route text differed, a missing ast-grep silently losing routes. `--xy` is an addition to
a normal run, so it must never leave less than a normal run does. CLAUDE.md's rule on
commands that stop was narrowed to overwriting, with the maintainer's yes.

**Alternatives.** Stopping before work for every missing piece (the previous rule):
loses work the code alone could do. Clicking candidate buttons found on the page:
could press something destructive; only steps the code names, and never risky ones, are
tried. Dropping x/y when not measured: loses verified work that is still safe to check
against.

## 2026-10-09 — the measured layout ships with the skill, readable

**Decision.** A skill with a measured layout gets `references/layout.json`: the window
size, the open steps, and every measured field's x/y, width and height plus its offset
from the anchor, marking the landmarks the fill call checks. SKILL.md names it and says
to read it only for a check by hand, and to measure again before any click.

**Why.** The maintainer exported the farmland plugin and found no x/y. Export was not at
fault (the exported SKILL.md was byte-identical): the chain Chromium → `layout.json` →
`page.json` kept all 13 boxes, but SKILL.md held only 8 landmarks, relative to the anchor,
as an unlabelled `{w,h,a,b}` argument of the fill call. Five measured boxes never reached
the skill, and the rest could not be recognised.

**Alternatives.** Putting every box into the fill call: costs tokens on every fill for
data the check does not need. Copying the raw probe capture: it is evidence and stays in
`.skillgendev/`; the reference is built from the page model.

## 2026-10-09 — views: one walk for steps, tabs, dialogs and revealed fields

**Decision.** A page model holds `views`: the parts hidden until a click, in fill order,
each with the clicks that reach it from the part before and the fields it shows. Claude
reads them from the code (prompt version 3); skillgendev never runs code Claude writes. The
skill's own setter walks the views in one call and stops before submit, and the probe
reaches every view with that same setter, filling earlier parts with example values,
then measures it; conditional fields are shown by setting their controller. Deduced
views are trusted once their fields appear in the browser.

**Why.** On the maintainer's onboarding form only step 1's first tab (10 of 39 fields)
got x/y: skillgendev had no notion of parts behind clicks. The maintainer asked for one
reusable way, driven by Claude's reading of the code, that covers steps, tabs, dialogs
and dynamic fields, with everything captured into the exported skill.

**Alternatives.** A separate connector program between Claude and Chromium: the probe
already drives Chromium through Playwright, CLAUDE.md rules out MCP, and an exported
skill must run in any AI's browser with nothing installed. Letting Claude write page
JavaScript: untestable, and a wrong guess could submit or delete. Clicking stored x/y at
fill time: selectors survive layout changes that coordinates do not, so positions stay a
check and a reference.

**Also fixed.** ast-grep searched `node_modules` in projects without `.gitignore` (72 junk
routes on formtest); the route-objects pack was TypeScript-only, so `.js` routers found
nothing (now `route-objects-js`); `.vue` components were not linked to their routes; and
Git Bash's rewritten routes (`/C:/Program Files/Git/...`) were saved. Each has a test.

## 2026-10-09 — found on the real onboarding form: budget, stale routes, uncheckable views

**Decisions.**
- The SKILL.md token budget (5000) is a reported note, not a failure; the 500-line limit
  stays a failure. Over the budget, optional fields first move to `references/fields.md`
  (`generate.folder.fit_skill_text`). A 39-field, four-step form's fill call alone is
  about 13 KB because it must carry every selector, and refusing that skill threw away a
  correct one. Squeezing the script onto longer lines was rejected (CLAUDE.md forbids it).
- Re-discovering routes replaces a route's saved code files with the ones found now, and
  drops a saved route no source finds any more when it was found automatically and the
  developer never named, skipped, opened or generated it. Routes that are Windows paths
  are dropped. Before, 62 junk routes and a router file that pulled every page into one
  slice stayed in `routes.json` forever.
- When a component is resolved, the route's slice starts from it alone; the router file
  that declares every route is the entry only when nothing better is found.
- Each field in the fill call is tried on its own: one selector the page cannot parse
  (an analysis wrote `#…_{idx}_…`) made the whole call throw. A view none of whose
  selectors parse is trusted after its clicks instead of stopping the walk. The prompt
  now forbids template selectors.

**Result on the form.** x/y for 32 of 39 fields (was 10); one call walked three tabs and
four steps, filled 26 fields, stopped before submit.

## 2026-10-10 — ChatGPT plugin export; every plugin's author is chapeee

**Decision.** `export-chatgpt` writes one skills-only ChatGPT plugin in the portable
Agent Plugins layout that ChatGPT and Codex share: `plugin.json` at the root (schema
`agent-plugins.org/schemas/1.0.0`, OpenAI listing text under
`extensions.com.openai.interface`), `skills/`, `assets/icon.svg` and `MANIFEST.sha256`.
`--zip` puts the plugin in one top-level folder, as OpenAI's upload requires. Each
skill's `compatibility` line names ChatGPT instead of Claude and Cowork; nothing else in
a skill changes. The index page stays out. A plugin name that breaks the naming rules,
or a `<plugin>:<skill>` identity over 64 characters (OpenAI's limit), stops the export
before anything is written.

Every exported plugin manifest, ChatGPT's and `export --plugin`'s
`.claude-plugin/plugin.json`, names the author `chapeee` (`export.PLUGIN_AUTHOR`).
The ChatGPT listing's `developerName` is the same.

**Why.** The maintainer asked for a command that makes the skills easy to use in
ChatGPT, with the author always `chapeee`. OpenAI's plugin docs (October 2026) accept
plugins that hold only skills, with no MCP server, so the export keeps the no-MCP rule.
The author overrides "nothing may assume our names" for this one field; the maintainer
chose it for both plugin manifests when asked.

**Alternatives.** An Apps SDK app: it is an MCP server, which CLAUDE.md rules out. A
custom GPT: it has no file format to import, and its Actions need a hosted API. Uploading
the `export --plugin` zip, which OpenAI's portal converts from `.claude-plugin/`: that
works only for the portal, keeps the Claude-only compatibility line, and has no listing
text or icon. A `--author` flag: the maintainer wants the author fixed.

**Not settled.** `version` is skillgendev's version, as for the Claude Code plugin. OpenAI
asks for a new version on each re-upload, so regenerated skills re-uploaded under the
same skillgendev version need a confirmation in the portal.

## 2026-10-10 — four fill methods in every skill; the AI picks by what its browser can do

**Decision.** `generate` gives every skill four ways to fill its form, and `SKILL.md`
opens with "Choose how to fill": decide what the browser tool can do on this page, then
use the first method it supports.
1. JavaScript in the page: the existing one-call setter, then `scripts/fill.js`.
2. Locators: `references/locators.md`, each field's role, name, CSS selector and a
   Playwright-style action (`fill`, `selectOption`, `check`, `click`, `setInputFiles`),
   grouped by the view it shows in.
3. Browser actions: click, type and choose by visible label, in table order.
4. By hand: `references/manual-steps.md`, numbered steps by labels and sections.

Any key method 1 cannot set (after `fill.js`) is finished with method 2 or 3. The skill
warns that direct writes can fail in sandboxed browsers, protected pages,
framework-controlled forms and read-only page proxies. Each skill also gets eval 4,
"this browser cannot run JavaScript". Every export copies all four.

The setter now writes values through the prototype's setter and clicks boxes, as
fill.js already did: a browser test showed the old `el.value = …` reporting `ok` while a
framework-controlled form's state stayed empty.

**Why.** The maintainer found that some AIs (ChatGPT's browser) do not let a page script
write, and asked that the consuming AI choose the method, JavaScript first, then
Playwright-style locators, then the rest. Building the methods in `generate` rather
than in one export keeps every skill identical to the one `validate` checked, and gives
Claude the same fallbacks when it works from screenshots or meets a blocked page.

**Alternatives.** Generating the methods only in `export-chatgpt`: Claude and Cowork
users would lose them, and an exported skill would differ from the validated one.
Playwright code instead of locator data: the AIs that fill pages do not run Playwright,
and the fill scripts may not depend on anything. Browser actions first: one tool call
per field, so a 39-field form costs 40 or more calls instead of one. Putting locators
and manual steps in `SKILL.md`: over the size budget on long forms; they are read only
when chosen.

**Not settled.** An AI that cannot run JavaScript still reads the setter's lines in
`SKILL.md` on every fill (155 lines, about 8 KB, on the bench). Moving the setter to a
file would cost an AI that can run it one extra read.

## 2026-10-10 — the ChatGPT export is one skill with a file per page

**Finding.** The maintainer's upload of a two-form plugin was refused: a ChatGPT upload
accepts exactly one `SKILL.md` per zip, and ours had one per page (`skills/<page>/`).
The uploader found both, three levels deep, so it searches the whole archive and counts.

**Decision.** `export-chatgpt` now bundles every page skill into one skill folder named
after the plugin (`generate/bundle.py`):
- `skills/<name>/SKILL.md` is the only `SKILL.md`: a table of forms (title, route, what
  is on the page, which file to read) and the rule to read exactly one of them. About
  25 lines, so a fill reads it plus one page file.
- each page's body becomes `references/<skill>/page.md`, its scripts
  `scripts/<skill>/…`, its other references `references/<skill>/…`, and every
  `scripts/…` or `references/…` path inside those files is rewritten to match.
- `evals/` is left out. It is a developer test file, not skill content, and it was the
  only text in the export still naming Claude.
- the bundled skill is checked with `check_skill_files` after bundling.

This keeps the zip a valid skills-only plugin as well (`plugin.json` at the root, one
skill under `skills/`), so the same zip suits the platform portal and the Skills upload.

**Why.** The maintainer asked for one entry-point `SKILL.md` that calls supporting
files. It also costs fewer tokens than before: the entry point is read on every request
and is small, while a page's 20 KB is read only when that form is asked for.

**Alternatives.** One zip per page: the maintainer wants one upload, and a form the user
names would then depend on which skill they installed. Putting every page's fields in
one `SKILL.md`: far over the size budget, and every fill would pay for every page.
Keeping the plugin layout and telling the maintainer to use only the platform portal:
the refusal would stay for the Skills upload, which is the one they used.

**Not settled.** Nothing verifies the upload end to end; the zip is checked against
OpenAI's documented package rules only (layout, manifest, listing text, icon, skill
headers, name lengths, text characters). The entry point's wording for picking a form
has not been tested with a real request in ChatGPT.

## 2026-10-10 — a skill upload takes one skill; a plugin may hold many

**Finding.** The maintainer's upload was refused by **Claude**, not only ChatGPT: "Zip
must contain exactly one SKILL.md file. Currently there are 2." The file was a plain
`export --zip` of a two-page app. Researching both products' own documentation:

- Claude's skill upload wants the skill folder as the archive's top level
  (`<skill-name>/SKILL.md`; a `SKILL.md` at the archive root is not recognised), the
  folder name equal to the frontmatter `name`, and no plugin manifest
  (anthropics/claude-code#92902 reports the plugin export being refused for that).
- ChatGPT's skill upload wants the same shape, one skill per archive.
- Both products' **plugin** paths accept many skills, but need a manifest and
  `skills/<name>/`: `.claude-plugin/plugin.json` for Claude Code, root `plugin.json`
  (Agent Plugins 1.0.0) for ChatGPT and Codex.
- Every product counts `SKILL.md` files anywhere in the archive, not at a fixed depth.

**Decision.** `export` gains `--one-skill`, which bundles every page into one skill
(`generate/bundle.py`, as `export-chatgpt` already did) and writes the skill folder
itself: no manifest, no index page, and `write_export(root_name=…)` names the archive's
single folder after the skill so `--out` cannot break the rule. One file serves both
Claude's and ChatGPT's skill uploads. A plain `export --zip` of several pages now says
in its output that an upload will refuse it and names the flag to use
(`cli.describe_export_use`). The README leads with the right command per destination.

**Why.** Three uploads failed in a row because the README told the maintainer to upload
the plain zip to Claude's skill settings, which has never been able to accept a
multi-page app. The failure was in the advice and the missing layout, not in the skill
content.

**Alternatives.** Making `--one-skill` the default: the per-page folders are the better
shape for a skills folder, where each page's own description decides when it triggers.
One zip per page: the maintainer wants one upload. Only fixing the ChatGPT export: the
refusal came from Claude.

**Not settled.** Nothing verifies an upload end to end; the archives are checked against
each product's documented rules only. Whether the entry point's table makes an AI pick
the right form is untested with a real request.

## 2026-10-10 — a page is sliced from its own component, never from the router

**Finding.** On the maintainer's app every route's slice was the same 32 files,
including all 11 other forms, and the analysis prompt was 14.9 KB per route. Slicing
from the resolved component gives 10 files. Two bugs in `pipeline.ensure_route`, the
path `generate --route` and `prepare` take:

1. It called `find_route_candidates(workspace, settings, None)` — **no graph**. Without
   one, a route's component identifier cannot be resolved to its file, so the only entry
   on offer is the router that declares every route.
2. `if found is not None and found.entry_files: return found` returned a saved entry
   unconditionally, so the wrong entry was never corrected. That contradicted
   `merge._merge_one`'s own rule, "the code is the source of truth: files found now
   replace the ones saved before", which `ensure_route` short-circuited before it ran.

**Decision.** `ensure_route` takes the graph and passes it to discovery; `generate` and
`prepare` load the graph before choosing routes. A saved entry is replaced when a graph
was available, because discovery can then resolve the component; without a graph the
saved files are left alone, since the router would be a worse answer than what is there.
`restore_skill_names` replaces the blunt rewrite of `routes.json` that a run made when it
wrote no skill: the developer's name is put back, while the code files discovered stay,
because they are facts about the code and not a choice.

**Why.** The AI reads the sliced files, so a 32-file slice costs about 3x the tokens and
time of a 10-file one on every route, and it hands the model 12 near-identical forms when
it should see one — an accuracy risk, not only a cost. Measured on the maintainer's app:
32 files → 10, with the saved entry corrected in place and the chosen skill name kept.

**Alternatives.** Telling developers to re-run `routes` to repair a workspace: the wrong
entry is invisible, and nothing says the slice is wrong. Replacing saved files
unconditionally: without a graph that would overwrite a resolved component with the
router. A hub heuristic ("an entry shared by several routes is a router"): more
machinery, and the real cause was the missing graph.

## 2026-10-10 — the fill call moves to `references/fill.md`; SKILL.md is ordered for truncation

**Finding.** Claude Code keeps only the first 5,000 tokens of an invoked skill after a
conversation is compacted, with 25,000 across all of them, and the Agent Skills spec
recommends a body under 5,000 tokens and 500 lines. Measured on the maintainer's app,
`SKILL.md` was 4,940 / 5,018 / 6,846 tokens for three forms, 40–48% of it the inline
fill call. The insurance form was over the budget, so its tail — submit and verify,
browser actions, gotchas — was silently dropped mid-session. A reader that cannot run
JavaScript paid for 8–13 KB of script it could never use, then read `locators.md` on top.

**Decision.** The call, the per-key statuses, the layout states, the views walk, the
short re-run call and `locate` move to `references/fill.md`, read at the moment of
filling. `SKILL.md` keeps a short "How to fill" that sends the reader there first, then
names the fallbacks by ability. Sections are ordered so that what a fill depends on
(fields, dependencies, rules, gotchas) comes before what explains an outcome (submit,
page mismatch), because the start of the file is what survives truncation.

JavaScript stays the way a form is filled, stated plainly rather than as one option
among four: it sets every field in one call and needs no screenshots. The other methods
are escape hatches for a browser that cannot run a page script, and every skill still
ships all of them.

**Result.** Bench: 280 lines and about 4,300 tokens to 95 lines and about 1,600.
The maintainer's three forms: 19,760 → 10,455 B (-48%), 20,072 → 11,507 B (-43%),
27,385 → 12,033 B (-57%), all now inside the 5,000-token activation budget. With the
script gone, optional fields no longer overflow into `references/fields.md` either.

**Why not a hard size gate.** The maintainer ruled it out: a budget that fails a build
throws away a correct skill. Size comes down by structure instead.

**Alternatives.** Keeping the call in `SKILL.md` for a one-call fill (the 2026-10-08
decision this reverses): that cost every reader the script whether or not it could run
it, and it was what pushed a real skill past the point of truncation. One extra file
read on the JavaScript path is the price, and the fill's total cost is unchanged.

## 2026-10-10 — heavy libraries are imported where they are used

**Finding.** `python -X importtime -c "import skillgen.cli"` cost 1.08s, of which 0.77s
was our own modules: `jsonschema` 320ms (through `skillgen.schema`, imported eagerly by
`analyze.runner` and `validate.spec`) and `PyYAML` 80ms (through `validate.spec`,
`routes.astgrep` and `routes.hintpacks`). Every command paid both, including `logs`,
`init` and `doctor`, which validate nothing and read no YAML.

**Decision.** Both are imported at the point of use: `schema._validator_class`,
`validate.spec.check_skill_md`, `astgrep.run_pack` and `hintpacks` file reading.
`tests/test_boundaries.py` asserts neither is in `sys.modules` after
`import skillgen.cli`, so the startup path cannot regress silently.

**Result.** `import skillgen.cli` 1.08s → 0.68s. Commands measured end to end:
`init` 1.38s → 1.26s, `export` 1.62s → 1.46s, the rest being `uv`'s own startup and
the interpreter (0.31s together).

**Alternatives.** Importing `cli`'s command modules lazily per command: a much larger
change for the same saving, and `cli.py` would no longer show what it depends on.
Vendoring a smaller validator: the schemas are the CLI's contract and JSON Schema
draft 2020-12 support is worth the one-off cost on the commands that need it.

## 2026-10-10 — the whole-run path refreshes entries, and the graph cache expires

**Findings, both the same class as the slice bug: cached state that is silently wrong.**

1. `generate --all` reads `routes.json` and never re-resolved a route's code files, so
   the `ensure_route` fix reached `--route` only. On the maintainer's app two of three
   routes still sliced the router, and so the whole app, after the fix.
2. `.skillgendev/cache/graph.json` had **no invalidation at all**. Once written it was
   reused by every `routes`, `generate` and `prepare` for ever; only `check` rebuilt it.
   A form added, a component renamed or an import changed left a graph that resolves a
   component to a file that has moved, or not at all — and the page is then sliced from
   the router again.

**Decisions.**
- `pipeline.refresh_entry_files` replaces the chosen routes' code files with the ones
  the code shows now, and `--all` calls it. It neither adds nor drops routes; that
  stays `routes`' job. Like `ensure_route`, it only acts with a graph, because without
  one the router is the only answer on offer and worse than what is saved.
- The cache records `built_at`, and `codegraph.find_graph_staleness` rebuilds when any
  file the graph holds has changed or gone, or a file was added beside them. That is one
  `stat` per file plus one per folder: on the maintainer's app, 24 files and 8 folders,
  and an unchanged run still takes 1.85s.

**Verified on the maintainer's app.** `generate --all --overwrite` corrected all three
entries in 2.69s. An unchanged run reuses the graph; touching a form rebuilds it
("EventRegistrationForm.vue changed"); adding a file beside the forms rebuilds it
("files were added or removed in src/views/forms"). All three skills then validate with
no notes, where `insurance-form` had been 6,701 tokens, over the activation budget.

**Token cost per route, measured on the smallest form.** The files the model must read
fell from 32 files and 228,466 bytes (about 57,100 tokens) to 9 files and 21,100 bytes
(about 5,275 tokens), 91% less, and the prompt from 14,924 to 4,832 bytes.

**Alternatives.** Making `generate --all` re-discover routes through `discover_routes`:
it would add and drop routes as a side effect of generating, which belongs to `routes`.
Hashing file contents for the cache: a read of every file on every command, where mtime
and folder stamps answer the same question from `stat` alone. A time-to-live: it would
either rebuild when nothing changed or trust a stale graph, and the cost of being wrong
is a silently bad slice.

## 2026-10-10 — `prompt.md` carries the answer schema, and the rules explain `type`

**Finding.** A transcript of an agent generating one skill showed about fifteen round
trips spent guessing the analysis contract: fields at the root that are not allowed,
`evidence` as strings instead of objects, `lines` instead of `line`, HTML control names
as `type`, conditions without `op`. It ended up reading skillgendev's own source to find
the schema. The cause: `build_analysis_prompt` says "Return one JSON object that matches
the page-analysis schema" and never includes it. The schema reached only `claude -p`, as
`--json-schema`; the interactive path that `/skillgendev` and the driver skill are built on
had no way to know it.

**Decision.** `prepare_route` writes the schema into `prompt.md` with the
`add_schema_to_prompt` helper that already existed for the Windows shim. It adds 9,292
bytes (about 2,300 tokens) to a prompt, once per route, in place of a round trip per
guess — each of which costs reading an error and rewriting the whole analysis.

The rules also now say what `type` is: the value, not the control, with the HTML names
called out as wrong. The schema lists the valid values, but nothing said how to choose
one, which is why an agent answered `radio`, `checkbox`, `select` and `textarea`.

**`PROMPT_VERSION` is not bumped.** The fingerprint covers the sliced files and the
prompt version, not the prompt text, so saved analyses stay reusable. They were produced
against the same schema and were already validated against it; the new text prevents
future guesses rather than invalidating past answers.

**On the slice and the code graph.** Measured after the slice fix: of the nine files
sliced for the smallest form, six are referenced by the page itself and two
(`fakeServer.js`, `storage.js`) are reached transitively — and those carry the
server-side validation the analysis needs for `is_server_checked`. The slice is
well-targeted now, so no further filtering is worth the risk of dropping a rule.

## 2026-10-10 — the AI's own limit is a wait, not work to do by hand

**Finding.** A real run reported `You've hit your session limit · resets 8:40pm`, and
skillgendev handed the route back as `action: analyse` — "read the code and write the
analysis yourself". That is the most expensive possible response: writing an analysis by
hand spends far more of the same limit than waiting for it, and an earlier transcript
shows an agent doing exactly that for about fifteen round trips. Two causes:

1. `describe_claude_failure` matched `usage limit`, `rate limit` and `credit`, but the
   real wording is **`session limit`**, so it fell through unrecognised.
2. Even when matched, the only effect was a hint appended to the message. The need was
   still `analysis`, which means "the agent does this instead".

**Decision.** `Need.LIMIT` is its own need. `analyze.runner.is_limit_reached` classifies
the reason (session, usage or rate limit, quota, credit, too many requests), `cli` picks
`LIMIT` over `ANALYSIS` for it, and the handoff answers with `action: ask`, the reset
time, and the same command to run afterwards — with `prompt` and `write` empty, so
there is nothing for the agent to write. The driver skill says to tell the user and
stop, never to do the analysis instead.

**Also corrected: an earlier diagnosis of mine was wrong.** The repeated
`claude exit code 1; stderr:` lines in the logs were read as an unknown failure. They
are a DEBUG line; the reason was reported correctly on the next line, and the cause was
always the account's limit. Nothing in the subprocess handling was broken.

**Not covered by tests.** The `claude -p` path is exercised by unit tests with stubs and
by `--analyzer file`/`replay` end to end, never by a real call, because a real call
spends the maintainer's quota. Every claim about that path rests on reading the code and
on messages from the maintainer's own runs.

## 2026-10-10 — the page inventory reports what is clickable, and what not to click

**Decision (phase A of the discovery loop the maintainer designed).** `probe/extract.js`
now returns, beside the fields it always did, every clickable thing on the page: label,
role, a replayable `step` (a selector when it names one element, else `text:Label`),
whether it is visible, disabled or collapsed, what it expands (`aria-controls`), and
three warnings — `chrome`, `leaves` and `risky`.

**Why the warnings exist.** Tried on the maintainer's running app first: a walk that
clicked every non-risky control navigated through the page's own menu into four other
forms and "discovered" 122 fields, none of which belonged to the page being analysed.
The maintainer predicted exactly this ("you might think this will also collect
unnecessary elements, such as headers and navigation buttons"). With the three flags,
the insurance form's 29 clickables become 13 worth trying — its collapsible panels and
its row adders — and the onboarding form's 23 become 5: its three tabs, Add Education
and Next.

`risky` also covers Reset and Clear, not only submit and delete: discovery clicks what
the inventory offers, and a reset would throw away everything filled so far.

**Nothing else changes yet.** The new list is added beside the field list, and
`probed_page_from_dict` reads what it needs by key, so every existing consumer is
untouched. The loop that uses it comes next.

**Also found.** Fields hidden behind a step are often already in the DOM, marked not
visible (`v-show` and CSS hiding): the insurance form has 27 of its fields there on
load. So a single inventory already answers most of a page, and the loop is needed for
content that is genuinely not mounted until a click.

## 2026-10-11 — Graphify's own `explain` and `path`, through its command line

**Decision (phase B).** The analysis prompt carried a flat list of paths: an analysis
was told which files build a page and nothing about how. It now carries Graphify's own
account of the page's component, asked with `graphify explain <component> --graph …`.
The maintainer chose the command line over calling Graphify's functions: it is the
public interface, and the same two commands they use by hand.

`graph/connections.py` builds the graph those commands read with
`graphify extract <repo> --code-only --no-cluster --no-dedup --out <cache>`, which stays
on the AST pass so no model is called and no API key is needed. It lands in
`.skillgendev/cache/graphify-out/graph.json`, beside the collapsed graph, and is rebuilt
only when `find_graph_staleness` says the code moved — the same question the collapsed
graph already asks, with Graphify's graph file as the stamp. `find_path` is there for
the discovery loop to ask how a page reaches a part defined elsewhere.

**Cost, measured on the maintainer's app.** The first `prepare` 11.5s, including
Graphify's build; the next 4.6s with the graph reused. The graph is 357 KB, 468 nodes
and 692 edges. One `explain` per route, bounded at 40 lines.

**What an analysis is told now.** For the insurance form: degree 22, and every
connection with its relation and line — `DragDropUpload.vue` (so the page has an
upload), `ToggleSwitch.vue`, `CollapsiblePanel.vue`, `validation.js`, `useBasicForm.js`,
and `<-- index.js [imports_from]`, the router that reaches it.

**Graphify is an aid, never a requirement.** A missing CLI, a non-zero exit, a timeout
or an answer of "No node matching" all leave the prompt with the file list it always
had. Tests cover each of those paths with a stubbed command rather than a real build.

**Alternatives.** Calling `graphify.serve`'s own helpers on the extraction we already
hold in memory: no second build and about a second instead of eleven, but the helpers
are private by name and would break on an upgrade. The maintainer preferred the public
interface, and the build is cached between runs.

## 2026-10-11 — discovery writes down every state it reaches

**Decision (phase C).** `probe/journal.py` holds what discovery has learnt about one
page, in `.skillgendev/pages/<skill>/discovery.json`. Each state of the page is recorded by
the clicks that reach it, with the fields seen there, what the page offered to click,
which of those clicks have been tried, and whether anything is left worth trying. The
journal also keeps notes a later run should not have to find out again, and counts the
model calls spent so a cap can be enforced.

**Why it exists.** Every state costs a browser and, where a reader chooses the click, a
model call. The maintainer's requirement was explicit: a step must be repeatable and
nothing already found may have to be found again. So the journal is written after each
state, and a run that stops, fails or runs out of model calls resumes from the last one.

**It only ever grows.** A state is recorded once by its own clicks; re-reading that
state replaces its record and no other. A click already tried is never tried twice, and
a field seen in two states is reported once, in the order it was first seen.

**A record from another layout is ignored rather than misread**: the schema number is
checked, and an unreadable file starts discovery over instead of failing a run.

## 2026-10-11 — the browser stops rediscovering what the code already states

**The architecture, settled with the maintainer.** There are two sources of truth, and
each is asked only what it alone knows:

| Source | Knows | Never asked |
| --- | --- | --- |
| the code, through Graphify and the analysis | meaning, validation, why a field appears, what opens what | whether a selector resolves, real option text, positions |
| the live page, through one script | real selectors, labels and options, what is clickable, x/y | why anything happens |

**What this removed.** `probe.runner.find_behaviour` set every dropdown and checkbox in
turn, reloading the page between each, and diffed the result to learn which fields are
conditional and which option lists depend on another. That is 85 lines spending most of
a probe's time to rediscover what a `v-if` states plainly. Measured against the
analyses already on disk, it also did it worse:

- On the maintainer's event form it found the ticket-type and dietary rules but **missed
  `card_number`** (it never tried `payment_method = "Card"`), and split one rule
  (`dietary != "None"`) into four rows, one per option.
- On the bench it found the two facts the analysis already held, and nothing else.
- Neither reached the final model: the merge records `source=['EXTRACTED']` at 0.85,
  because the walk's controller keys (`tickettype`) never matched the analysis's
  (`ticket_type`). It was discarded work.

**What replaced it.** `reveal_values` reads the code's own conditions and sets the
controller that brings a conditional field on screen, so the probe can still fill and
prove it. One value per rule, read rather than searched for.

**Measured on the bench, same 21 fields:**

| | time | proven |
| --- | --- | --- |
| the walk | 14.7s | 16 |
| walk deleted, nothing in its place | 12.2s | 13 |
| walk deleted, revealing from the code | **7.2s** | **16** |

Half the time, the same result. Conditions and dependencies now come from the code
alone, which is where they were already coming from.

**Also wired in.** The inventory from phase A is carried into the probe capture, and
`compile/unopened.py` compares the live page with the model: a field the page shows that
the model lacks, and a panel that looks like it holds part of the form and was never
opened, are reported in the run's notes with the `--open` flag to use. Previously a part
the code reading missed was silently absent.

## 2026-10-11 — the analysis is shown the live page, not only the code

**Finding.** `summarize_probe` has always existed to put what the browser saw into the
analysis prompt, and both callers passed `None` instead, with the comment "the analysis
reads code only; a probe that saw the wrong screen must not steer it". So the function
was never used: the analysis guessed a page's fields and the parts behind a click from
source alone, while a capture of the real page sat on disk beside it.

**Decision (phase D).** The analysis is given the capture, with the original concern
answered rather than ignored: `probe_for_route` hands one over only when its URL path
matches the route being analysed, and never an empty one. A capture from another route,
or from a sign-in page that stood in for this one, is logged and dropped.

The summary now also carries `clickable`: what a person can click, with a step that can
be replayed, once the page's own menus, links away from it, costly controls and hidden
ones are left out. On the bench that is one entry, `Add reference -> #add-reference`,
out of everything on the page. The rules say plainly that a button is never a field but
one that opens part of the form belongs in `open` or `views`, which is what the list is
for.

**Why this is the whole of phase D.** The plan had been a loop: inventory, ask a model
what to click, click it, inventory again, repeat. Two measurements made that
unnecessary. Fields behind a step are usually already in the DOM, marked not visible —
27 of 32 on the maintainer's insurance form — so one reading answers most of a page. And
the code already states what opens what, which is what the analysis reports as `views`.
What was missing was not a loop but a fact: the analysis could not see the page. Now it
can, and `compile/unopened.py` reports anything it still failed to account for.

## 2026-10-12 — generated output does not invalidate the source graph

**Decision.** Code-graph staleness checks ignore `.skillgendev/`, the configured skills
folder, `dist/` and the generated index files. A root-directory mtime change still
compares the current recognized source-file inventory with the graph, so a real source
addition or deletion rebuilds the graph without rebuilding after every generated output
write. The richer Graphify query graph is built once per `generate`/`prepare`/regenerate
run and shared by all route analyses.

The route scanner also skips router packs whose file globs have no matching source files,
and a generate run reuses the automatic route candidates it already found. On the React
fixture this reduced the named-route subprocess count from 14 to 4: two relevant
ast-grep scans, one Graphify explanation and Git metadata.

**Analysis reuse.** The analysis fingerprint now covers the rendered prompt, schema,
probe summary, Graphify connections, route/app context and every slice file, rather than
source bytes alone. A cache hit is logged explicitly; an old code-only fingerprint is
not treated as proof that the new prompt inputs match.

**Probe boundary.** The explicit `probe` command continues to report runtime conditions
and dependent option lists for its detailed capture. The generation `--xy` path does not
run that controller walk: it stays code-first and measures the code-built page, so the
extra browser reloads remain outside ordinary generation. The probe walk is covered by
the bench test and its findings are not allowed to override the code-first model.
