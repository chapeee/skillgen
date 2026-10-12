# skillgendev

**A framework- and domain-agnostic compiler that reads an app's code, route by route,
and writes one build-ready Agent Skills folder (`SKILL.md` + `scripts/fill.js`) per
page, so Claude, Cowork or any AI that accepts Agent Skills can fill that page's form
with few tokens.**

> Status: pre-alpha. Install from PyPI: `uv tool install "skillgendev[probe]"`.

- [Why](#why)
- [Which frameworks does it support?](#which-frameworks-does-it-support)
- [Install](#install)
- [Use it on your own project](#use-it-on-your-own-project)
- [Logs and debugging](#logs-and-debugging)
- [Testing (the `tests/` folder)](#testing-the-tests-folder)
- [Command reference](#command-reference)

## Why

Without a skill, Claude rediscovers a form on every task: it takes screenshots,
clicks field by field, and guesses which options exist and which fields depend on
which. A generated skill tells Claude once what every field means, what it accepts,
the order to fill it in, and how to check the result. It then fills the whole page in
one browser call.

1. **Generate** (developer, once per change): skillgendev finds the app's routes, picks
   out the code that builds each page, has Claude Code read that code, and writes one
   skill folder per page. A running dev copy is optional; with one, a Playwright probe
   checks every fact on the real page.
2. **Use** (anyone): add a skill folder to Claude, Cowork or any AI that accepts Agent
   Skills. With its built-in browser, the AI opens the page and fills it. Nothing needs
   to be installed and no MCP server is involved.

```text
skills/acme-signup/
  SKILL.md                    # fields, rules, dependencies, and the script that fills them
  scripts/fill.js             # the fallback engine, read only for fields the skill cannot do
  references/locators.md      # each field's role, label, selector and action, for locator tools
  references/manual-steps.md  # the form as plain steps by visible labels
  evals/evals.json            # four synthetic test requests
```

### Four ways to fill, chosen by the AI

Not every AI can run JavaScript in a page; ChatGPT's browser, for example, may not let
it write there. So every skill carries four ways to fill the same form, and `SKILL.md`
tells the AI to decide first what its browser tool can do, then use the first one it
supports:

1. **JavaScript in the page**: one call fills every field and reports each one. The
   skill warns that direct writes can fail in sandboxed browsers, protected pages,
   framework-controlled forms and read-only page proxies; any field the call cannot set
   moves on to the next method.
2. **Locators** (`references/locators.md`): for tools that act on elements by role,
   label or selector, such as Playwright's `fill()`, `selectOption()`, `check()` and
   `click()`. It is data, not code, so nothing needs installing.
3. **Browser actions**: click, type and choose each field by its visible label.
4. **By hand** (`references/manual-steps.md`): numbered steps by labels and sections,
   for an AI working from screenshots or for the user.

Every export (`export`, `export --plugin`, `export-chatgpt`) copies all of them, so the
same skill works in Claude, Cowork, ChatGPT or any other AI.

## Which frameworks does it support?

**Any web app whose forms render as HTML in a browser.** Frameworks matter only for
the first step, *finding the list of routes*. skillgendev tries these sources in order and
merges what they find:

| Source | Covered today |
| --- | --- |
| Folder routing (built in) | Next.js (app and pages router), Nuxt, SvelteKit, Astro |
| Routes declared in code (ast-grep, installed with skillgendev) | React Router, route objects (Vue Router, Angular, data routers), Express, Flask, Django, Laravel, Rails, Spring MVC, ASP.NET Core attributes, Phoenix |
| Graphify's own route nodes | ASP.NET Razor Pages (`@page "/x"`), Dart / Flutter navigation |
| **Claude Code reading the code graph** | **Any other stack**: Go, Rails `resources`, conventional MVC routes, custom routers, CMSs… |
| You | `skillgendev routes --route /checkout` |

How the Claude step works: Graphify does not name routes in most stacks, but its links
show *hubs*, files such as a router that link to many controllers, views or pages.
skillgendev ranks those likely router files and gives Claude Code the map ("this file
links to these files"). Claude reads them read-only and returns the routes with their
entry files. It runs automatically when no other source finds a route, or on demand
with `skillgendev routes --all --ask-claude`. The prompt is saved in
`.skillgendev/route-listing-prompt.md` so you can see what was asked.

Everything after route discovery is framework-agnostic: Claude Code reads code in any
language, Graphify links files in about 30 languages, and the optional probe only looks
at the rendered page. To teach skillgendev a router once and for all, add a small YAML file
under `hintpacks/` (see [`hintpacks/README.md`](hintpacks/README.md)); no Python needed.

Tested end to end on React Router, Next.js and Flask apps. The Rails, Spring, ASP.NET,
Phoenix and Laravel hint packs are tested on small sample apps, and the Claude step was
tried live on Rails and Go samples.

## Install

skillgendev is on [PyPI](https://pypi.org/project/skillgendev/). You need Python 3.10+.

```bash
uv tool install "skillgendev[probe]"   # or: pipx install "skillgendev[probe]"
skillgendev doctor --fix                # checks tools; downloads Chromium for the probe
```

On macOS or Linux with [Homebrew](https://brew.sh) (includes the probe extra):

```bash
brew install chapeee/tap/skillgendev
```

Code-only use needs no extra: `uv tool install skillgendev` (or `pip install skillgendev`).
To work on skillgendev itself, install it from a clone:

```bash
git clone https://github.com/chapeee/skillgen.git
cd skillgen
uv tool install --editable ".[probe]"
```

- ast-grep, which finds routes declared in code (Laravel, Rails, Express...), is
  installed with skillgendev. (`.[astgrep,probe]` from older notes still works.)
- The `probe` extra lets `generate --xy` measure where each field sits (x/y) on a
  running dev copy. Leave it out for code-only use. `skillgendev install` downloads the
  Chromium it needs.
- Upgrade with `uv tool upgrade skillgendev` (or `pip install --upgrade skillgendev`).
- From a clone, `--editable` means `git pull` updates your `skillgendev` at once.
- **One-step local install from a clone** (like `npm link`, for contributors):
  `.\scripts\install-local.ps1` on Windows or `scripts/install-local.sh` on macOS and
  Linux.
  It removes any old install, clears uv's cache, installs your clone globally in
  editable mode, checks that `skillgendev` points at your clone and downloads Chromium.
  Rerun it after changing dependencies. Options: `-RunTests` / `--run-tests`,
  `-NoExtras`, `-SkipChromium`, `-Uninstall`. If PowerShell blocks the script, run
  `powershell -ExecutionPolicy Bypass -File .\scripts\install-local.ps1`.
- Batch generation (`generate --all`) calls [Claude Code](https://claude.com/claude-code):
  install it and log in once (`claude`). `skillgendev doctor` shows whether it is found.

## Use it on your own project

Run everything from your project's root folder. Git is not required, but with it
skillgendev records which commit each skill was made from, and `skillgendev check` can tell
which skills went stale.

```bash
cd ~/code/my-app
git init                          # only if the project is not a git repository yet

skillgendev init --app-name "My App" # creates .skillgendev/ (add `.skillgendev/` to git; its secrets/ and cache/ are ignored)
skillgendev routes --all             # finds routes, writes .skillgendev/routes.json
```

Check `.skillgendev/routes.json`. Add missing routes with `skillgendev routes --route /path`.
Running `routes --all` again updates it from the current code: a route's code files are
replaced by the ones found now, and routes the code no longer has are removed, unless you
named, skipped or generated them. Folders such as `node_modules` and `dist` are never
searched.
Set `"skip": true` on routes you do not want, or edit a `skill` name.

You can give a real page address instead of the pattern. With
`--route /cms/locations/states/134`, skillgendev finds the code of
`/cms/locations/[level]/[id]` and reads that. If two patterns fit equally well it
guesses nothing and the analysis starts with no files, so give the pattern route
then. Apps inside one repository (an admin app and a main site side by side) are all
found.

Then generate skills. skillgendev's commands are run by an AI agent, not typed by you:
the agent reads skillgendev's instructions, runs the commands and asks you whatever needs
a decision. The instructions (`claude/skills/driver/SKILL.md`) are plain Markdown, so
any agent can follow them; `skillgendev install` sets them up for Claude Code.

```bash
# A. Inside Claude Code (recommended to start): Claude does the reading in your session
skillgendev install                  # adds /skillgendev to Claude Code, and Chromium for --xy
claude                            # then type:  /skillgendev /signup    or   /skillgendev all

# B. Batch: skillgendev calls `claude -p` once per route
skillgendev generate --route /signup --name my-signup    # one route, exact skill name
skillgendev generate --all --name myapp                  # every route, names start with myapp-
```

Run `skillgendev install` again after you update skillgendev, so `/skillgendev` gets the new
instructions; it copies them rather than linking them.

Some facts in your code may be unclear. skillgendev keeps those out of the skill and asks
you instead:

```bash
skillgendev questions                # open questions
skillgendev answer q1a2b3c "yes"     # answer one (yes / no / code / page / a value)
skillgendev generate --all --overwrite   # regenerate to apply answers
skillgendev validate                 # check every skill folder
```

**Use the skills** in Claude, Cowork, ChatGPT or any AI that accepts Agent Skills. Which
export you need depends on where it goes, because a skill upload takes **one skill at a
time** while a plugin may hold many (see [Which export goes where](#which-export-goes-where)):

- **Claude or ChatGPT skill settings (upload):** `skillgendev export --one-skill --zip`,
  then upload `dist/skill/<name>.zip`. Every page becomes one skill with one `SKILL.md`.
- **Claude Code or Cowork (your own machine):** copy a folder from `skills/` into
  `~/.claude/skills/`. One skill per page, each triggering on its own description.
- **A plugin to install or publish:** `skillgendev export --plugin --zip` for Claude Code,
  `skillgendev export-chatgpt --zip` for ChatGPT and Codex.

Then ask the AI to fill the page; it opens it in the built-in browser and uses the skill.

Keep skills current after code changes:

```bash
skillgendev check --since HEAD~1 --regenerate
skillgendev index                    # skills-index.html: every skill and a graph of the app
```

### Normal, or with x/y

`generate` has two modes, and the command chooses:

| Command | What you get |
| --- | --- |
| `skillgendev generate --route /x --name my-skill` | **Normal.** Everything from the code. No browser, no x/y. Works on every page |
| `skillgendev generate --route /x --name my-skill --xy` | **Everything normal gives, plus x/y.** Opens the page on your dev copy in Chromium and measures where each field sits |

`--xy` only adds. It never removes a field, changes what the skill says about one, or
adds a question; if it cannot measure the page, you get the normal skill and the AI is
told why (see [When something is missing, the AI asks you](#when-something-is-missing-the-ai-asks-you)).
The run reports how many fields got x/y (`x/y for 16 fields`). With x/y, the skill
checks the live page against that layout before it writes anything: if the page looks
different, or a dialog covers it, it fills nothing and the AI inspects the page as
usual. Every measured position also ships with the skill, in
`references/layout.json` (window size, each field's x/y, width and height, and its
offset from the first field); the AI reads it only when it has to check the page by
hand, and measures a field on screen again before clicking it. `export` copies it with
the skill. A different screen size is fine; it is checked by structure, not by pixels. It
adds roughly 1,250 tokens to each fill.

`--xy` needs a dev or staging copy (never production; nothing is ever submitted). Set
its address once with `skillgendev init --url http://localhost:3000`, or pass `--url`. If
you forget, the AI asks you for it before anything runs:

```bash
skillgendev generate --route /signup --name my-signup --xy
```

If the page needs you to be signed in, you do not have to know that beforehand. The
skill is written from the code anyway, and the AI asks whether to open a browser window
so you can sign in. You sign in, close the window, and it measures x/y.

`skillgendev probe --route /x --url http://localhost:3000/x/7` looks at one route in detail:
which fields it finds, which values it can set, what a submit sends. Use it to see what
the probe sees; it does not change a skill.

#### Steps, tabs, dialogs and fields that appear later

Many forms do not show every field at once: a multi-step form shows one step at a time,
tabs show one panel, a dialog opens with a button, and some fields appear only for one
choice. skillgendev handles all of them the same way, from your code:

1. **Claude reads the code** (the Graphify code map gives it the page's files) and lists
   every hidden part as a *view*: its name, the click that reaches it from the part
   before, and the fields it shows. Fields that appear for a value (*Laptop* only when
   *Work location* is *Remote*) are recorded as conditions instead.
2. **`--xy` walks every view in Chromium.** For each one it opens the page fresh, makes
   the clicks with the same script the skill uses (filling the earlier parts with safe
   made-up values, so a *Next* that checks the step lets it through), waits for the
   fields to appear, and measures them. A conditional field is shown by setting the field
   it depends on. Nothing is ever submitted, and a click such as *Save* or *Delete* is
   never made. A view Claude only deduced is used once its fields really appeared.
3. **The skill walks them too.** One call fills every step: it opens a part only when a
   value belongs there, checks its fields appeared, fills them, closes a dialog with its
   *Done* button, and stops before *Submit*. If the page refuses to move on (a required
   field is missing), it stops and reports the page's own error messages.

**Example.** On an onboarding form with three tabs on step 1 and four steps:

| View | Click | Fields |
| --- | --- | --- |
| Address tab | "Address" | country, state, city |
| Emergency Contacts tab | "Emergency Contacts" | contact name, phone |
| Step 2: Employment | "Next" | department, job title, laptop (for remote work) |
| Step 3: Payroll | "Next" | direct deposit, bank |
| Step 4: Review | "Next" | agree to policy |

With `--xy` every field of every step gets x/y, and `references/layout.json` says which
view each was measured in. Claude decides what to click by reading the code; skillgendev
does the clicking with one tested script, in Chromium while generating and in the
filling AI's own browser later. No new code is written per page.

#### `--open`: when the form is hidden behind a button

Some pages do not show their form straight away. You have to click something first: a
**Settings** button, a tab, or an **Edit** link. Until you click it, the fields are
hidden.

skillgendev cannot measure fields it cannot see, so it has to click that first.

**Usually skillgendev finds the click itself.** When Claude reads your page's code (with
the code graph from Graphify), it looks for what opens the form, for example a
**Page settings** button that opens a side panel, and records it. `--xy` then makes that
click in Chromium and checks that the fields appear. The skill makes the same click when
it fills the page. You do not type anything.

If Claude only guessed the click, or the click looks like it could change data (such as
**Save** or **Delete**), skillgendev does not use it. It asks you first, in
`skillgendev questions`. Answer `yes`, or give the right click, with several separated by
`;`:

```bash
skillgendev answer q1a2b3c "text:Page settings"
```

**`--open` sets the click yourself.** Use it when skillgendev did not find the click, or
found the wrong one. Your `--open` always wins over what the code analysis says.

**Example.** On this page the fields sit inside a side panel, and the panel opens when
you click the **Page settings** button:

```bash
skillgendev generate --route /cms/locations/states/134 --name state-location --xy --open "text:Page settings"
```

What happens:

1. skillgendev opens the page in Chromium.
2. It clicks **Page settings**. The panel opens and the fields appear.
3. It measures where each field is (x/y).
4. It writes the skill.

Later, when an AI fills the page with this skill, the skill clicks **Page settings** too,
but only if the panel is closed. If the panel is already open, it leaves it alone: a
second click would close it again.

**How to say what to click**

| You write | It clicks |
| --- | --- |
| `--open "text:Page settings"` | the button, link or tab whose text, or tooltip, is exactly *Page settings* |
| `--open "#settings-button"` | the element this CSS selector finds |

Use `text:` when you can. It is easier to read, and it works in every terminal. In
Windows PowerShell, a CSS selector with quotes inside it, such as
`button[title="Page settings"]`, loses those quotes and stops working.

**More than one click.** Repeat `--open`, in the order you would click:

```bash
skillgendev generate --route /account --name my-account --xy --open "text:Settings" --open "text:Profile"
```

**You only type it once.** skillgendev saves it for that page in `.skillgendev/routes.json`
(as `"open"`), and keeps it when routes are found again. Next time `--xy` is enough:

```bash
skillgendev generate --route /cms/locations/states/134 --name state-location --xy
```

To change it, run `--open` again with the new click, or edit `"open"` in `routes.json`.

**When you do not need it.** If the form is on screen as soon as the page opens, leave
`--open` out.

### Recreating a skill

A skill that already exists is never replaced by accident. `generate` stops before any
work, reports it as already there, and `/skillgendev` asks you whether to recreate it.
`--overwrite` recreates it; your notes in the skill's user section are kept.

```bash
skillgendev generate --route /signup --name my-signup --overwrite
```

If the page's code has not changed since the last analysis, skillgendev reuses that
analysis instead of reading the code again, so recreating a skill after answering
questions is quick and costs no tokens. When any file the page is built from changes,
it analyses again. To force a fresh analysis, delete
`.skillgendev/pages/<skill>/analysis.json`. `check --regenerate` recreates stale skills
without asking: the flag is the go-ahead.

A recreated skill replaces the old one only when it passes every check. If a check
fails, the old skill and its saved page data stay exactly as they were.

### When something is missing, the AI asks you

You never have to switch settings or fix a half-finished run by hand. When skillgendev
cannot finish a page, it says why and what to do next, and the AI running it (Claude
Code through `/skillgendev`, or another) does that step or asks you. Then it runs the
command again, and skillgendev carries on where it stopped.

| What happened | What the AI does |
| --- | --- |
| skillgendev could not ask Claude Code to read the code (not signed in, a usage limit, not installed) | Reads the code itself and writes the analysis. You are not asked anything |
| `--xy`, but no dev address is set | Writes the skill from the code, then asks you for the address |
| Your dev server is not running | Writes the skill from the code, then asks you to start it |
| Chromium is not downloaded | Writes the skill from the code, then asks whether to download it now (about 150 MB) |
| The page asks you to sign in | Writes the skill from the code, then asks whether to open a browser window so you can sign in |
| The form is hidden behind a button (a closed panel) | Tries the click the code points to. If the fields appear, that click is proven and saved. Only if nothing works does it ask which button opens the form |
| The skill already exists | Asks whether to recreate it, before doing anything |

`--xy` always gives you everything a normal run gives. When x/y cannot be measured, the
skill is still written from the code, and x/y from an earlier run is kept for every
field whose selector has not changed. The skill says how many fields were seen on the
live page, so the AI filling it knows what was checked in a browser and what comes from
the code only.

**Example.** In Claude Code you run `/skillgendev /cms/locations/states/134` and ask for
x/y. The page needs a sign-in:

1. skillgendev writes the skill from the code and says: *the page showed a sign-in page*.
2. The AI asks you: *"This page asks you to sign in before x/y can be measured. Open a
   browser window so you can sign in now?"*
3. You say yes. A Chromium window opens. You sign in and close it.
4. The AI runs the command again. skillgendev reuses the analysis (the code did not
   change), measures x/y and replaces the skill.

Nothing is analysed twice while the page's code is unchanged. Two pages built by the
same code file (such as `/states/95` and `/states/134`) need no extra analysis either.

For whoever builds an agent: each result then has status `needs` (or `exists`) and a
`next` object, and the exit code is 3. `next.action` is `analyse` (read `next.prompt`,
write the analysis to `next.write`) or `ask` (ask the developer `next.ask`, run
`next.run` on a yes). Then run `next.then`.

### Which export goes where

Every product has two ways in, and they want different shapes. A **skill upload** takes
one skill at a time: its archive must hold exactly one `SKILL.md`, with the skill folder
as the archive's top level and no plugin manifest. A **plugin** may hold many skills, but
needs its manifest and `skills/<name>/`. Uploading the wrong one fails with
*"Zip must contain exactly one SKILL.md file"*.

| Where it goes | Command | What you get |
| --- | --- | --- |
| Claude or ChatGPT skill settings (upload) | `export --one-skill --zip` | `dist/skill/<name>.zip` → `<name>/SKILL.md` plus a file per page. One skill, no manifest |
| Claude Code, Cowork (your own machine) | `export` | `skills/<page>/` folders to copy into `~/.claude/skills/`. One skill per page |
| Claude Code plugin | `export --plugin --zip` | `.claude-plugin/plugin.json` + `skills/<page>/`, author `chapeee` |
| ChatGPT and Codex plugin ([platform](https://platform.openai.com/plugins)) | `export-chatgpt --zip` | `plugin.json` + one skill under `skills/<name>/` + `assets/icon.svg` |

`export --one-skill` and `export-chatgpt` both bundle, so both hold exactly one
`SKILL.md`. A plain `export --zip` of several pages does not, and says so when you run it.

### One skill, a file per page

Bundling keeps every page whole and makes the entry point cheap to read:

```text
acme/
  SKILL.md                                  # the only SKILL.md: a table of forms, ~25 lines
  references/acme-signup/page.md            # that page's fields, rules and fill call
  references/acme-signup/locators.md        # and its other fill methods
  references/acme-signup/manual-steps.md
  references/acme-signup/fields.md, layout.json
  scripts/acme-signup/fill.js               # its fallback engine
  MANIFEST.sha256
```

The entry point gives each form's title, route, what is on it and the one file to read,
then says to read exactly one. A fill costs that table plus one page file, so adding
pages does not make a fill dearer. Each page keeps all four fill methods, and the paths
inside its files are rewritten to match the layout above. `evals/` and the index page
stay out: they are for you, not for the AI.

The skill folder is named after the skill (`--name`, else the app prefix), because every
product requires the folder name and the `name` in `SKILL.md` to match. With `--zip` that
holds whatever you call the file: `--out dist/download` still zips as `acme/SKILL.md`.

### Upload it to ChatGPT

ChatGPT has the same two ways in:

- **Skill upload:** `skillgendev export --one-skill --zip`, then upload it in ChatGPT's
  skill settings, the same file Claude takes.
- **Plugin:** `skillgendev export-chatgpt --zip` writes the portable Agent Plugins layout
  that ChatGPT and Codex share — `plugin.json` at the root (name, version, description,
  author `chapeee`, and the listing name, tagline and icon), one skill under
  `skills/<name>/`, and `assets/icon.svg`. Upload it at
  [platform.openai.com/plugins](https://platform.openai.com/plugins) as a skills-only
  plugin; OpenAI scans and reviews it before you choose to publish. For yourself, copy
  the folder to `~/.codex/plugins/acme`, list it in `~/.agents/plugins/marketplace.json`,
  restart the ChatGPT desktop app and install it from the Plugins Directory:

  ```json
  {
    "name": "local",
    "plugins": [
      {
        "name": "acme",
        "source": { "source": "local", "path": "./.codex/plugins/acme" },
        "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
        "category": "Productivity"
      }
    ]
  }
  ```

Either way the export stops and says so when `--name` is too long: a skill name is at
most 64 characters, and ChatGPT counts `<plugin>:<skill>` against that limit.

### On Windows

Use PowerShell. Git Bash rewrites anything that starts with `/` into a Windows path, so
`--route /signup` arrives as `C:/Program Files/Git/signup` and skillgendev reports no such
route. In Git Bash, put `MSYS_NO_PATHCONV=1` in front of the command, or pass the
skill's name instead of its route (`--route my-signup`).

## Logs and debugging

Every command writes a full debug log in your project, so anyone running skillgendev can
see exactly what happened and share it:

```bash
skillgendev logs                     # the latest log (last 60 lines) and its path
skillgendev logs --list              # recent logs
skillgendev generate --all -v        # also print progress to the terminal (-vv for debug)
```

- Logs live in `.skillgendev/logs/` (the newest 30 are kept). They are gitignored and never
  exported.
- They record the version, your command, timings, the files sliced for each route, each
  Claude Code call (prompt size, exit code, error output), what the merge kept, and every
  check that failed.
- On an error, skillgendev prints `Full log: <path>`.
- Other files worth reading when something looks wrong, per route in
  `.skillgendev/pages/<skill>/`:
  - `prompt.md`: what Claude was asked.
  - `analysis.json`: what Claude answered.
  - `slice.json`: which files it read.
  - `page.json`: the merged model.
  - `evidence.jsonl`: where each fact came from.
  - `changes.json`: what changed since the last run.

## Testing (the `tests/` folder)

There are three levels of tests. The first two run without Claude, the network or an
API key. The third is the real check that Claude and Cowork use a skill well.

### What is in `tests/`

| Path | What it is |
| --- | --- |
| `tests/test_<module>.py` | Unit tests, one file per source module (a test enforces this) |
| `tests/test_boundaries.py` | Project rules as tests: Graphify only in `graph/`, Playwright only in `probe/`, no `print` outside `cli.py`, no hard-coded tool name, no MCP |
| `tests/fixtures/react-router-spa/` | Example app: React + React Router (routes found by ast-grep) |
| `tests/fixtures/nextjs-app/` | Example app: Next.js app router (routes found from folders) |
| `tests/fixtures/flask-jinja/` | Example app: Flask + Jinja templates (Python, server-rendered) |
| `tests/fixtures/*/analyses/` | Recorded Claude analyses, so tests never call Claude |
| `tests/fixtures/*/expected/` | Golden output: the skills skillgendev must produce for that app |
| `tests/bench/` | The test bench: one page with every widget, its server, its skill, 14 cases |

### 1. Unit and end-to-end tests (fast, no browser)

From the skillgendev clone:

```bash
uv sync --all-extras              # once
uv run pytest                     # about 650 tests in a few seconds
```

This runs every module's tests, plus the full CLI (`init`, `routes`, `generate`,
`index`, `export`, `check`) on the three example apps. Each run's output is compared
with the golden files in `expected/`.

If you change the generator on purpose, regenerate the golden files and review the
diff before committing:

```bash
uv run pytest --update-golden
git diff tests/
```

Also run the linters, as CI does:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

### 2. Browser tests (real Chromium, still no Claude)

```bash
uv run playwright install chromium   # once
uv run pytest -m browser             # about a minute
```

This starts the bench server on a free port and opens the bench page in Chromium.

- It runs `scripts/fill.js` for every bench case: fill, follow-up, server rejection,
  wrong host, missing field.
- It checks what the server received.
- It runs the probe against the bench and checks that it creates **zero** records.

If Playwright's own Chromium does not match your Playwright version, point the tests at
another Chromium: `SKILLGEN_CHROMIUM=/path/to/chrome uv run pytest -m browser`.

### 3. The test bench in Claude and Cowork (manual, the real thing)

This checks that Claude reads the skill and behaves well: it asks once for missing
values, never invents options, treats page text as data, and stops on the wrong host.

**Start the bench page** (standard library only, no install):

```bash
python3 tests/bench/serve.py         # http://localhost:8765/apply
```

Open http://localhost:8765/apply yourself to check that it loads. The browser Claude
uses must reach `localhost`, so run this on the same computer as Claude in Chrome or
the Claude desktop app.

**Add the bench skill to Claude**, in a second terminal:

```bash
python3 tests/bench/check.py zip       # Claude or Cowork: upload tests/bench/dist/bench-apply.zip in Skills settings
python3 tests/bench/check.py install   # Claude Code: copies it to ~/.claude/skills/bench-apply/
```

**Run a case:**

```bash
python3 tests/bench/check.py list         # the 14 cases
python3 tests/bench/check.py prompt 01    # the prompt to paste, the follow-up answer, what to look for
python3 tests/bench/check.py reset        # clear earlier submissions
```

Paste the prompt into a new Claude or Cowork conversation. When Claude asks a question,
reply with the follow-up the case shows. Then check the result:

```bash
python3 tests/bench/check.py check 01     # PASS or FAIL, with the differences
```

`check` compares what the server received with what the case expects. Also judge by
hand what the case lists under "should" and "should not"; for example, that Claude
asked once rather than three times.

| Case | What it checks |
| --- | --- |
| 01 happy path | Every value given: one fill call, one submit |
| 02 company conditional | Fields that appear only for "Company" are filled |
| 03 missing required | Claude asks once for every missing value, then finishes |
| 04 dependent options | Region waits for its server-loaded list after Country |
| 05 ambiguous option | Two cities match: Claude asks which |
| 06 not an option | An unknown country: Claude lists the real choices, invents nothing |
| 07 client rule | A value breaking a rule: Claude explains and asks |
| 08 server rejection | Server rejects the username: Claude fixes only that field |
| 09 tree, chips, checkboxes | Tree path, chips and a checkbox group |
| 10 rows and rich text | Three repeated rows and a longer statement |
| 11 page text is data | An option label with instructions inside is not obeyed |
| 12 file upload | Upload through the browser's upload action (attach `tests/bench/files/sample-id.pdf`) |
| 13 without JavaScript | Fill by label from the table, no scripts |
| 14 wrong host | Page on 127.0.0.1 instead of localhost: Claude stops |

When a pull request changes generated skills, paste a results table into it (template
in [`tests/bench/README.md`](tests/bench/README.md)).

### CI

`.github/workflows/ci.yml` runs levels 1 and 2 on every pull request (Python 3.10 and
3.13). It needs GitHub Actions to be enabled for the repository.

## Command reference

### What each command does

Here is every command in plain words, in the order you would use them. Your AI agent
runs them for you, for example through `/skillgendev` in Claude Code, but you can run them
yourself too. Every option is in the table at the end.

**Set up (once)**

- **`skillgendev install`**: adds the `/skillgendev` command to Claude Code, so you can ask
  Claude to make skills. It also downloads Chromium, which `--xy` needs.
  Example: `skillgendev install`
- **`skillgendev init`**: sets skillgendev up in your project. It creates a `.skillgendev/` folder
  for its working files. Give it your app's name, and your dev copy's address if you
  want x/y.
  Example: `skillgendev init --app-name "My App" --url http://localhost:3000`
- **`skillgendev doctor`**: checks that everything skillgendev needs is installed, and tells
  you what is missing. `--fix` downloads Chromium.
  Example: `skillgendev doctor`
- **`skillgendev login`**: opens a browser window so you can log in to your dev copy once.
  The login is saved, so `--xy` can open pages that need it.
  Example: `skillgendev login --url http://localhost:3000/login`

**Find your pages**

- **`skillgendev routes`**: finds the pages (routes) in your app's code and lists them in
  `.skillgendev/routes.json`. Open that file to rename a skill, skip a page, or add one it
  missed.
  Example: `skillgendev routes --all`

**Make skills**

- **`skillgendev generate`**: makes one skill for a page. This is the main command. When
  it cannot finish, it says what to do next and exits with code 3 (see
  [When something is missing, the AI asks you](#when-something-is-missing-the-ai-asks-you)).
  Example: `skillgendev generate --route /signup --name my-signup`
  - Add `--xy` to also measure where each field is on the page.
  - Add `--open "text:Page settings"` when the form is hidden behind a button and
    skillgendev did not find that button in your code by itself.
  - Add `--overwrite` to make a skill again when it already exists.
- **`skillgendev prepare`**: gets one page ready for Claude to read its code inside your
  Claude Code session. `/skillgendev` runs it for you; you rarely need it by hand.
  Example: `skillgendev prepare --route /signup`

**Answer what skillgendev is not sure about**

- **`skillgendev questions`**: lists what skillgendev could not decide from your code. Those
  facts stay out of the skill until you answer.
  Example: `skillgendev questions`
- **`skillgendev answer`**: answers one question. Then run `generate` again with
  `--overwrite` to update the skill.
  Example: `skillgendev answer q1a2b3c yes`
- **`skillgendev add-rule`**: adds your own rule to a skill, such as "Age must be 18 or
  more". With `--check` the skill also checks the value before it fills it. With
  `--global` the rule goes into every skill.
  Example: `skillgendev add-rule my-signup "Age must be 18 or more" --check "age min 18"`

**Check and share**

- **`skillgendev validate`**: checks that your skills are correct and contain no secrets.
  Example: `skillgendev validate`
- **`skillgendev check`**: after you change your code, tells you which skills are now out
  of date. `--regenerate` makes them again.
  Example: `skillgendev check --since HEAD~1 --regenerate`
- **`skillgendev index`**: writes `skills-index.html`, one page that shows every skill and
  a map of your app.
  Example: `skillgendev index`
- **`skillgendev export`**: copies your skills out, ready to share or upload. It checks them
  and scans them for secrets first. `--one-skill` bundles every page into one skill, which
  is what Claude's and ChatGPT's skill uploads accept.
  Example: `skillgendev export --one-skill --zip`
- **`skillgendev export-chatgpt`**: packs your skills into one ChatGPT skill, ready to
  upload or to add to the ChatGPT desktop app. One `SKILL.md`, one file per page. Same
  checks and scan as `export`.
  Example: `skillgendev export-chatgpt --zip`

**When something goes wrong**

- **`skillgendev logs`**: shows in detail what the last command did.
  Example: `skillgendev logs`
- **`skillgendev probe`**: opens one page on your dev copy and shows what the browser finds
  there. It is only for looking; it does not change any skill.
  Example: `skillgendev probe --route /signup`

### Every option

Every command accepts `--json` (for scripts and CI), `--root <folder>` (run on another
project) and `-v` / `-vv` (more output).

| Command | What it does |
| --- | --- |
| `skillgendev init` | Create `.skillgendev/` in your project. `--app-name "My App"`, `--url http://localhost:3000` (dev copy for the probe), `--environment dev\|staging\|production`, `--name myapp` (skill-name prefix), `--analyzer claude-code\|file\|replay` |
| `skillgendev routes` | Find routes and write `.skillgendev/routes.json`. `--all`, `--route /x` (add by hand, repeatable), `--include "admin/*"`, `--exclude "api/*"`, `--name prefix`, `--no-graph`, `--ask-claude` (also let Claude list routes from the code graph), `--no-claude` (never call Claude) |
| `skillgendev prepare` | Write the analysis prompt for one route so Claude Code can answer it in your session. `--route /x`, `--name my-skill`, `--no-graph` |
| `skillgendev generate` | Generate skills. `--route /x` or `--all`; `--name` (exact name with `--route`, prefix with `--all`); `--xy` (also measure x/y on the dev copy; only adds); `--open STEP` (with `--route`: what to click before the form shows, a CSS selector or `text:Label`; repeat for several; saved to `routes.json`); `--url` (the dev copy's address; implies `--xy`); `--code-only` (never open a browser; the default); `--analyzer claude-code\|file\|replay`; `--replay-dir`; `--concurrency 4`; `--description "…"`; `--include` / `--exclude`; `--force` (retry routes marked as having no form); `--overwrite` (recreate skills that already exist; without it they are left as they are and reported); `--no-graph`. Exits 3 when a route waits for a next step (`next` in `--json`) |
| `skillgendev questions` | List facts skillgendev needs you to confirm. `--skill name`, `--all` (include answered) |
| `skillgendev answer <id> <answer>` | Answer a question (`yes`, `no`, `code`, `page` or a value) |
| `skillgendev add-rule <skill> "<rule>"` | Add a rule to one skill, or to every skill with `--global`. `--check "field ^A"` compiles a machine check into `fill.js` |
| `skillgendev validate [skill…]` | Check skill folders against the Agent Skills spec and scan them for secrets |
| `skillgendev index` | Write `skills-index.html` (graph and skill cards) and `skills-index.json` |
| `skillgendev check` | List skills made stale by code changes. `--since HEAD~1`, `--regenerate`, `--replay-dir`, `--no-graph`. Exits 1 when something is stale |
| `skillgendev export` | Copy skills out for sharing, after checks and a secret scan. `--zip`, `--one-skill` (bundle every page into one skill with one `SKILL.md`, for an upload; written to `dist/skill/<name>`), `--plugin` (Claude Code plugin, author `chapeee`), `--name`, `--out folder` |
| `skillgendev export-chatgpt` | Pack every page into one ChatGPT skill (one `SKILL.md` plus a file per page; `plugin.json`, author `chapeee`), after checks and a secret scan. `--zip` (one zip to upload), `--name` (plugin and skill name; default the skill prefix), `--out folder` (default `dist/chatgpt/<name>`) |
| `skillgendev probe` | Probe one route on a running dev copy. `--route /x`, `--url http://…/x/7` (for routes with parameters) |
| `skillgendev login` | Log in once in a browser window; the session is saved for probing. `--url` |
| `skillgendev logs` | Show the latest run log. `--list`, `--lines 60`, `--count 10` |
| `skillgendev install` | Add `/skillgendev`, its subagent and its skill to Claude Code, and download Chromium for `--xy` when the probe extra is installed. `--target ~/.claude` (or `./.claude` for one project); `--no-chromium` (skip the download) |
| `skillgendev doctor` | Check Python, Graphify, Claude Code, ast-grep and Playwright, and where `skillgendev` runs from. `--fix` downloads Chromium for the probe |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The design is in [docs/spec.md](docs/spec.md)
and decisions are logged in [docs/decisions.md](docs/decisions.md).

## Licence

Apache License 2.0.
