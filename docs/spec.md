> **Note.** This is the design spec as written. Project decisions in `CLAUDE.md` and
> `docs/decisions.md` override it: no MCP anywhere, skills target Claude and Cowork
> with their built-in browser, code-only generation is the default and the Playwright
> probe is an optional extra.

# Code-to-Skill Compiler — Final Spec (v2)

Oct 8, 2026 · @raa

## 1. Verdict and re-verification log

**Build it as a general code-to-skill compiler: give it a repository and one route (or all routes), and it writes one build-ready `SKILL.md` folder per page.** Each skill teaches Claude what every field means, what it accepts, which fields depend on which, and how to fill and verify the page. Claude stops rediscovering the code on every task. Nothing in the design names a framework, a form library or a business domain.

I re-checked every v1 decision against your corrections and against source code (Graphify, the Agent Skills spec, Playwright MCP, Chrome DevTools MCP, Anthropic's `skills` and `claude-code` repos). Eight decisions changed:

| # | v1 decision | v2 status | Why |
| --- | --- | --- | --- |
| 1 | Graphify = locator + change impact, not form understanding | **Kept** | Re-confirmed in source: the Vue extractor masks the template; routes are extracted only for Dart and Razor; no HTTP-call extraction |
| 2 | Framework adapters (Vue template, JS HTTP, Laravel) as the core | **Reversed** | Hard-coded frameworks break your main rule. Replaced by layers every stack shares — the code graph, the rendered page, the network — plus Claude Code reading the code for meaning. Optional ast-grep "hint packs" only speed things up |
| 3 | One recorded fill in the MVP | **Kept, upgraded** | Now an automatic **probe**: Playwright fills safe values, watches what appears and what loads, and intercepts and cancels the submit, so nothing is saved |
| 4 | Default execution = in-page API call | **Changed** | Default is one scripted fill through the page's own inputs. It runs the app's own frontend logic and works on any framework; an API call skips that logic. API mode is out of the MVP |
| 5 | One app skill + a `PAGE.md` per page | **Reversed** | One route = one skill, each self-contained and shareable alone — your requirement, and the Agent Skills guide's "coherent unit" advice |
| 6 | Python runtime (`formfill.py`) on the client | **Replaced** | Replaced by `scripts/fill.js`, run through the browser tool's evaluate call. Every supported browser tool runs JavaScript in the page; Python cannot reach the page and adds round trips |
| 7 | Rules live in `form.json`; prose only for the rest | **Changed** | `SKILL.md` is now self-sufficient. `fill.js` gets its checks from the same page model, so the skill works with or without the script |
| 8 | Drop Semgrep | **Kept** | ast-grep (MIT, tree-sitter based, YAML rules) added as optional |
| 9 | Framework CLIs (`artisan route:list`) first | **Generalised** | Any framework CLI that prints routes is an optional probe; none is required |
| 10 | Claude Code as the reasoning engine at generation time | **Kept, made concrete** | Interactive (`/skillgendev` command), batch via headless `claude -p --json-schema` per route, or one subagent per route |
| 11 | \~9x fewer tokens per fill | **Recomputed** | \~25x for a 40-field fill (about 8 tool calls instead of \~138), because the fill is now one browser call. Still a model; measured in MVP week 8 |
| 12 | Evidence + confidence on every fact | **Kept** | Adds the `RUNTIME_PROBED` source |
| 13 | Drift via `graphify update` + `affected` | **Kept** | Re-confirmed in `affected.py` and `watch.py` |
| 14 | Credentials never leave the browser | **Kept** | Plus: probing runs only on dev or staging, with submits intercepted |
| 15 | Property and real-estate examples | **Removed** | All examples are now generic |
| 16 | Laravel + Vue MVP scope | **Replaced** | MVP is tested on three apps in three different stacks |
| 17 | "Claude preloads every skill's name and description" | **Verified** | Spec: about 100 tokens of metadata per skill load at startup. 40 skills ≈ 4k tokens, so descriptions are capped near 300 characters |
| 18 | Ad-hoc skill format | **Changed** | Output now follows the [Agent Skills spec](https://agentskills.io/specification), so skills also work in Claude, Codex, Cursor, Gemini CLI, GitHub Copilot and the other 40+ listed clients |

## 2. What the product is

**A compiler from application code to page skills.** It does once, automatically, what a developer otherwise explains to Claude again and again: what each field represents, what type of value it takes, which options are allowed, which fields depend on others, how the form is structured, what data must be entered, and how the page behaves.

It has two phases with different users:

| Phase | Who | Where | What happens |
| --- | --- | --- | --- |
| **Generate** | The developer | Claude Code, on the app's repository (+ optionally a running dev copy) | Routes are found, each page is analysed, one skill folder is written per page, plus a skill index page |
| **Use** | Anyone the skills are shared with | Claude, Claude Code or Cowork, with a browser tool | Claude loads the one skill for the page in play and fills it, asking only for missing values |

*(Pipeline diagram: generate once per change, use on every task.)*

Only the skill folders and the index page leave the developer's machine; at use time, Claude reads one small skill and fills the page through the user's own browser tab.

### Design principles

1. **Framework-agnostic.** The tool works out the stack itself. No one tells it "this is Vue" or "this uses a tree component".
2. **Domain-agnostic.** No business vocabulary is built in. Field meaning comes from the app's own code, labels and validation.
3. **One route = one skill**, each with a meaningful, spec-valid name. A collection of focused skills, never one giant skill.
4. **`SKILL.md` is the deliverable.** It is self-sufficient, follows the Agent Skills spec, and can be shared alone. Scripts and references in the folder only make it faster.
5. **Claude Code does the understanding; deterministic tools do the measuring.** Claude reads any code in any language. Graphify, Playwright and the validators supply facts Claude should not guess.
6. **Derived from code, verified on the running page** when one is available. Each fact records where it came from.
7. **Few tokens at use time.** A skill is small, loads only when its page is in play, and fills the page in one browser call.

## 3. How it stays framework- and domain-agnostic

**It never depends on knowing the framework. It reads layers every web app shares, and lets Claude Code read the code for meaning.** Vue, React, Next.js, Angular, Svelte, server-rendered templates, a tree component, a homemade widget: all of them end up as files with imports, as elements in a page, as reactions to input, and as HTTP requests.

| Layer | Why every stack has it | What it gives the skill | Tool |
| --- | --- | --- | --- |
| Code graph | Every repo is files that import each other | The page slice (the files that build this page) and change impact | Graphify (tree-sitter, about 30 languages) |
| Rendered page | Every framework ends as HTML elements with accessibility roles | Fields, labels, types, required, limits, options, sections, visibility, stable selectors | Playwright (accessibility snapshot + DOM) |
| Behaviour | Every app reacts to input events | Conditional fields, dependent options, async loading, client-side error messages | Playwright probe |
| Network | Every app talks HTTP | Option-loading requests, the submit payload's shape, the server's error format | Playwright request interception |
| Code meaning | Claude reads any language | What a field means, accepted values, enums, server-side validation, business rules, gotchas | Claude Code |
| Hint packs (optional) | Community-written YAML rules | Faster, cheaper extraction for common routers and validation libraries | ast-grep |

The tool detects the stack only to choose hint packs and route probes. When none match, nothing breaks: the probe and Claude Code still cover the page.

### Custom components and unusual widgets

A custom widget either exposes an accessibility role (combobox, listbox, tree, treeitem, grid) or it does not. The probe tries fill strategies in a fixed order, Claude reads the widget's own code when no strategy works, and the strategy that actually filled the field is written into the skill.

| Strategy | Used for |
| --- | --- |
| `native-input` | Text, number, email, date and similar inputs, textareas |
| `native-select` | `<select>`, single or multiple |
| `choice` | Checkbox and radio groups |
| `aria-combobox` | Searchable dropdowns and autocompletes: type, wait, pick the option by visible text |
| `aria-tree` | Tree pickers: expand nodes along a path, pick the item |
| `aria-listbox` | Custom lists and chip pickers |
| `rich-text` | Content-editable editors |
| `file` | Uploads; needs the browser tool's file-upload action |
| `steps` | Anything else: short generated steps, kept only if the probe proved they work |

### Without a running app

Code-only mode still works. Claude Code derives fields and selectors from the code, and the skill is marked `verified: false` in its metadata, with lower confidence on every fact. Running the probe later upgrades it in place.

### Domain-agnostic content

Field meaning is written in the app's own words, taken from labels, help text, validation messages and code. Example values are synthetic and generated from each field's constraints, never copied from real data.

## 4. Route discovery

**Two modes: one route (`skillgendev route /developer/kyc`) or every route (`skillgendev routes --all`, optionally `--include "developer/*"`).** Each route found becomes one entry in `routes.json`, and each entry with a form becomes one skill.

Routes are collected from five sources and merged; the user can always name a route directly.

| Source | How it finds routes | Covers |
| --- | --- | --- |
| 1. User | `--route /x` | Anything |
| 2. Route probes | Folder-based routing (a `pages/`, `app/` or `routes/` tree), router declarations found by ast-grep hint packs, and any framework CLI that prints its routes | Most frameworks, front and back end |
| 3. Graphify | Route nodes where its extractors emit them (Dart, Razor today); resolving a route's component to its page slice for every stack | Slice for every route |
| 4. Runtime crawl (optional) | Logged-in Playwright walk over same-origin links and menus, capped at N pages | Routes built at runtime or by a CMS |
| 5. Claude Code | Reads the app's entry files and lists routes in the `routes.json` schema when 2–4 find nothing or disagree | Anything unusual |

### Rules for what becomes a skill

- A route with editable controls (in code or on the rendered page) gets a skill. A route without any is listed in the index as `no form` and skipped.
- **One route = one skill.** A page with several forms (for example two tabs) becomes one skill with a section per form. The developer can split it in `routes.json`.
- A multi-step wizard that moves across routes (`/kyc/step-1` → `/kyc/step-2`) becomes one skill when the probe sees its Next button stay inside the flow.
- A route with parameters (`/projects/:id/edit`) becomes a skill whose first input is that parameter; the skill tells Claude to ask for it, or to find the record first.

### Skill names

Names follow the Agent Skills rules: lowercase letters, digits and single hyphens, at most 64 characters, identical to the folder name. The pattern is `<app>-<route-slug>`, with the page's purpose added when the route alone is vague.

| Route | Skill name | Description (trimmed) |
| --- | --- | --- |
| `/individual/account` | `acme-individual-account` | Fills the Individual Account form at /individual/account in Acme: identity, contact, address… |
| `/individual/property` | `acme-individual-property` | Fills the Individual Property form at /individual/property… |
| `/developer/kyc` | `acme-developer-kyc` | Fills the Developer KYC form at /developer/kyc: business identity, directors, bank details, documents… |
| `/developer/project` | `acme-developer-project` | Fills the Developer Project form at /developer/project… |
| `/projects/:id/edit` | `acme-project-edit` | Edits an existing project at /projects/{id}/edit… |

The description template is "Fills the *page title* form at *route* in *app*: *top field groups*. Use when asked to *verbs from the title and submit button* *object*." It stays under 300 characters, because every installed skill's description sits in Claude's context. Duplicate names get a numeric suffix, and the developer can rename any skill in `routes.json` before generating.

## 5. Per-route pipeline and the page model

**Every route goes through the same seven steps; only step 3 uses model tokens.** Steps 2 and 7 need a running dev or staging copy and are skipped in code-only mode.

1. **Slice.** Graphify walks from the route's entry file over `imports`, `calls`, `uses_component` and `dynamic_import`, three levels deep. Output: the files that build this page, ranked by distance and capped (default 40 files or about 60k tokens).
2. **Probe.** Playwright opens the page with a saved login and:
   1. reads the accessibility snapshot and the DOM for every editable control: label, role, type, name, required, limits, options, section, visibility and a stable selector (test id, then name, then id, then label; uniqueness checked);
   2. submits the empty form with the request intercepted, to collect client-side error messages per field;
   3. changes each select, combobox and choice field, then diffs the page and the network: fields that appear or vanish are **conditions**, option lists that change are **dependencies**, and the request that fetched them is recorded;
   4. fills every field with synthetic valid values using its strategy and reads the value back, so each strategy is **proven**;
   5. intercepts the submit request, records its body **shape** (keys and types, never values) and cancels it. Nothing is saved. `--real-submit` on a sandbox also records the success signal and the server's error format.
3. **Analyze.** Claude Code receives the slice's file list, the probe results and a JSON schema. It reads the code and returns, per field: what it means, accepted values and format, enum values and where they come from, server-side rules, confirmed or extra conditions and dependencies; and per page: business rules, success and failure signals, gotchas and open questions. It runs interactively, or headless with `claude -p "…" --json-schema page-analysis.schema.json` and read-only tools, one route per run or one subagent per route.
4. **Merge.** Deterministic code combines probe facts, code facts and Claude's analysis into `page.json`, gives each fact a confidence, and writes conflicts to `questions.json` for the developer.
5. **Generate.** Templates turn `page.json` into `SKILL.md`, `scripts/fill.js`, and `references/fields.md` when the page has more than about 40 fields.
6. **Validate.** Spec checks (name rules, folder match, description length and always quoted in YAML, frontmatter parses, body under 500 lines and about 5k tokens), model checks (every required field present, dependency graph without cycles, every selector unique on the probed page) and a secret and personal-data scan.
7. **Verify (optional).** Headless Claude Code with a browser tool runs two or three synthetic fill requests against dev, once with the skill and once without, following the evaluation method in Anthropic's skill-creator. Tool calls, tokens and success go into the skill index.

### The page model (`page.json`, internal)

```json
{
  "schema": "skillgendev.page/1",
  "route": "/developer/kyc",
  "skill": "acme-developer-kyc",
  "title": "Developer KYC",
  "verified": true,
  "sections": [
    { "id": "business", "label": "Business details", "fields": ["legal_name", "entity_type", "registration_no"] },
    { "id": "bank", "label": "Bank account", "fields": ["bank_name", "bank_branch", "account_no"] }
  ],
  "fields": {
    "entity_type": {
      "label": "Entity type", "means": "Legal form of the business",
      "type": "enum", "options": ["Private Limited", "LLP", "Partnership", "Proprietorship"],
      "required": true, "strategy": "native-select", "selector": "select[name=entity_type]",
      "source": ["RUNTIME_PROBED", "EXTRACTED"], "confidence": 0.98
    },
    "registration_no": {
      "label": "Registration number", "means": "Official registration ID of the company",
      "type": "string", "format": "uppercase letters and digits, exact length from the validator",
      "required_if": "entity_type in [Private Limited, LLP]",
      "strategy": "native-input", "selector": "#registration_no", "confidence": 0.9
    },
    "bank_branch": {
      "label": "Branch", "type": "enum", "required": true,
      "strategy": "aria-combobox", "selector": "[aria-label='Branch']",
      "options_from": { "depends_on": "bank_name", "load": "async", "pick_by": "visible text" }
    }
  },
  "dependencies": [["bank_name", "bank_branch", "options_from"], ["entity_type", "registration_no", "visible_if"]],
  "fill_order": ["legal_name", "entity_type", "registration_no", "bank_name", "bank_branch", "account_no"],
  "submit": { "selector": "button[type=submit]", "success": { "url_matches": "/developer/kyc/status" }, "field_error": "[aria-invalid=true]" },
  "rules": [{ "field": "account_no", "check": { "pattern": "^[0-9]{9,18}$" }, "source": "EXTRACTED" }],
  "gotchas": ["Branch options load only after Bank is chosen; wait for them."]
}
```

`page.json` stays on the developer's machine with its evidence. Only what Claude needs to fill the page reaches `SKILL.md`.

## 6. The generated skill

**Each skill is one self-contained folder whose `SKILL.md` alone is enough for Claude to fill the page.** The other files make it faster or cover very large forms.

```text
acme-developer-kyc/
  SKILL.md               # required: what Claude reads (under 500 lines, about 5k tokens)
  scripts/fill.js        # fill engine + this page's field map; run in the page in one call
  references/fields.md   # only for pages over ~40 fields: the less-used fields, by section
  evals/evals.json       # 3 synthetic test requests, per the Agent Skills evaluation guide
```

### A complete `SKILL.md` (generic example)

```markdown
---
name: acme-developer-kyc
description: "Fills the Developer KYC form at /developer/kyc in Acme Admin: business details, directors, bank account and documents. Use when asked to complete, submit or update a developer's KYC in Acme."
compatibility: Built for Claude and Cowork with the built-in browser; needs a logged-in Acme session.
metadata:
  generator: skillgendev 0.1.0
  route: /developer/kyc
  app-url: https://admin.acme.example
  verified: "true"
  source-commit: 9f3c2e1
---

# Developer KYC — /developer/kyc

Records a developer's legal and bank details for verification. Saving moves the developer to "KYC submitted".

## Before you start
- A browser is required. Open https://admin.acme.example/developer/kyc in the user's logged-in tab. If a login page appears, ask the user to log in; never ask for a password.
- Take values from the user's request. Ask once for every missing required field. Never invent IDs, numbers or option values.

## Fill (fast path)
1. Read `scripts/fill.js`, then run its contents with the browser tool's evaluate action, followed by
   `__fill({ "legal_name": "…", "entity_type": "LLP", … })` using the keys below.
2. It returns `{filled, missing, invalid, ambiguous}`. Ask the user about `missing` and `ambiguous`, then call `__fill` again with only those keys.
3. When nothing is left, run `__submit()`. It clicks Save, waits, and returns `{ok, url, errors}`.

## Fields — in fill order
| Key | Label | Accepts | Required | Notes |
|---|---|---|---|---|
| legal_name | Legal name | text, 3–120 chars | yes | as on the registration certificate |
| entity_type | Entity type | Private Limited · LLP · Partnership · Proprietorship | yes | controls Registration number |
| registration_no | Registration number | uppercase letters and digits | if Private Limited or LLP | hidden otherwise |
| incorporation_date | Date of incorporation | YYYY-MM-DD, not in the future | yes | |
| gst_registered | GST registered | yes · no | yes | yes shows GSTIN |
| gstin | GSTIN | 15 characters | if GST registered | |
| directors[].name | Director name | text | at least 1 | "Add director" adds a row |
| bank_name | Bank | option from the list | yes | list loads from the server |
| bank_branch | Branch | option from the list | yes | loads after Bank; pick by visible text |
| account_no | Account number | 9–18 digits | yes | |
| cancelled_cheque | Cancelled cheque | PDF or JPG, up to 2 MB | yes | use the browser tool's file upload; scripts cannot fill it |

## Dependencies and conditions
- Bank → Branch: Branch options load only after Bank is chosen.
- Entity type is Private Limited or LLP → Registration number appears and is required.
- GST registered = yes → GSTIN appears and is required.

## Rules
<!-- skillgendev:generated -->
- Date of incorporation cannot be in the future.
- Account number contains digits only.
<!-- skillgendev:user:start -->
- Legal name must start with "A".  `check: legal_name ^A`
<!-- skillgendev:user:end -->

## Submit and verify
- Success: the URL becomes /developer/kyc/status and the heading reads "KYC submitted".
- Failure: invalid fields get `aria-invalid`; `__submit` returns their messages by key. Fix only those keys and submit again.
- Tell the user the result, and any value the page changed after saving.

## Without JavaScript
If the browser tool cannot run JavaScript, fill the fields in table order with its form-input action, finding each by its label.

## Gotchas
- Branch stays empty until Bank is chosen; wait for it.
- Save stays disabled until the declaration checkbox at the bottom is ticked.
```

### Size budget

A field row costs about 25 tokens. Up to about 40 fields, every field is in `SKILL.md`. Above that, `SKILL.md` keeps the required and most-used fields and says exactly when to read `references/fields.md` ("read it when the user gives a value for a field not listed above"), which is how the spec intends progressive disclosure to work.

### User rules, global rules, and what stays private

- **Page rules** live between the `skillgendev:user` markers and survive every regeneration. `skillgendev add-rule acme-developer-kyc "Only allow names starting with A"` appends one there; inside Claude Code it also proposes a machine check (`check: legal_name ^A`), which is compiled into `fill.js`. Hand edits work the same way.
- **Global rules** are kept once in `.skillgendev/rules/global.md` and copied into every skill's rules at generate time, under "Rules for all pages". Copying is deliberate: each skill must work when shared alone.
- Rules can only add constraints; `add-rule` refuses one that loosens a rule the app enforces.
- **Internal** data (`page.json`, evidence, probe captures, questions) stays in `.skillgendev/`. **Public** output is only the `skills/` folders and the index page; `export` copies nothing else.

## 7. Runtime: how Claude uses a skill

**A typical fill is about 8 tool calls with no screenshots: open the page, read the skill's script, fill everything in one call, ask once for gaps, fill the rest, submit, report.**

1. The user asks ("complete KYC for Brightline Developers, LLP, …"). Claude matches the request to one skill by its description and reads `SKILL.md` (about 2–4k tokens).
2. Claude opens the route in the logged-in tab (1–2 calls).
3. Claude reads `scripts/fill.js` once (about 1.5k tokens plus about 20 per field) and runs it with `__fill(values)` in a single evaluate call.
4. The result lists what is `missing`, `invalid` or `ambiguous`. Claude asks the user once, then calls `__fill` with only those keys.
5. `__submit()` clicks Save and returns success or per-field server errors. Claude fixes only the named fields if needed, then reports.

### What `fill.js` does

The engine is the same file in every skill (about 150–200 lines, versioned); only the field map at its top differs.

- Walks the fields in fill order. For each, waits until it exists and is visible, which handles conditional fields.
- Applies the field's proven strategy. Native inputs get the native value setter plus `input`, `change` and `blur` events, which is how React, Vue, Angular and plain scripts all detect changes. Selects match by value or visible text; comboboxes type and pick an option; trees expand along a path; rich-text editors get content-editable input.
- Waits for dependent options to load (a mutation observer with a timeout) before filling the next field.
- Checks the compiled rules locally and reads each value back.
- Collects errors from `aria-invalid`, `role=alert` and the error text next to each field.
- `__submit()` briefly wraps `fetch` and `XMLHttpRequest` to catch the submit response's status and error body, whatever the framework, clicks the submit control, and waits for the success signal or errors.

### Where it runs

The client uses **Claude or Cowork with its built-in browser** (Claude in Chrome, or the browser inside the Claude desktop app). That browser already opens pages, clicks and fills fields by itself, so there is nothing to install: **no MCP server, no API keys, no extra tools.**

The skill relies on two things every such browser can do:

1. **Run JavaScript in the page** — the fast path: `fill.js` fills the whole form in one call.
2. **Fill a field by its label** — the fallback when scripts are blocked: Claude fills the fields one by one in the order of the skill's table.

Clicking around field by field and taking screenshots stays the last resort, only for widgets the skill marks as needing the user or manual steps. Either way, the skill removes rediscovery: Claude already knows every field, its accepted values, its dependencies and the fill order.

### When something goes wrong

| Situation | What the skill tells Claude to do |
| --- | --- |
| Required value missing | Ask the user once, listing all gaps |
| Option not found or several match | Show the closest choices from the live list; never invent one |
| Client-side rule fails | Fix the value or ask the user |
| Server rejects fields | Fix only the named fields; resubmit once |
| A field in the skill is not on the page | The app has changed: switch to the manual path and tell the user the skill needs regenerating |
| Login page, CAPTCHA, or 2FA | Hand over to the user, then continue |
| File upload | Use the browser tool's upload action with a file the user provides |

## 8. Tokens and credits

**Estimated: a 40-field fill drops from about 138 tool calls and 5.0M input tokens with computer use to about 8 calls and 0.18M with a skill — roughly 25x fewer tokens.** This is a model, not a measurement; MVP week 8 measures real pages both ways.

Assumptions: 15k tokens of fixed context per turn; a screenshot ≈ 1,400 tokens and the last 3 kept; 2.5 actions per field for computer use plus waits and one round of validation retries; for the skill, `SKILL.md` of 2.5k tokens plus 25 per field, the engine read and written once, and one round of follow-up questions. Most input tokens are cache reads, which cost less, but the ratio holds.

| Fields filled | Computer use: calls | Computer use: input tokens | Skill: calls | Skill: input tokens | Ratio |
| --- | --- | --- | --- | --- | --- |
| 10 | \~63 | \~1.7M | \~8 | \~0.17M | \~10x |
| 40 | \~138 | \~5.0M | \~8 | \~0.18M | \~25x |
| 100 | \~288 | \~15.9M | \~8 | \~0.2M | 50x+ |

The skill's cost barely grows with form size because the values travel in one call; computer use grows with every field and re-reads a longer history each turn. Wall time follows the call count: roughly 12–18 minutes against 1–2 minutes for 40 fields.

### One-time generation cost

| Step | Model tokens per route | Human time |
| --- | --- | --- |
| Slice, probe, merge, generate, validate | 0 | CPU only; a few seconds to a minute |
| Claude Code analysis (reads up to \~60k tokens of code) | \~0.1–0.3M processed, \~5–8k output | 0 in batch mode |
| Developer answers questions | 0 | \~2–5 minutes per route |
| Optional verify run (with and without skill) | \~0.5M | 0 |

For 40 routes that is roughly 4–12M tokens once, about the cost of one to three computer-use fills per page. Each skill pays for itself on its first use, and regeneration after a code change touches only the routes that changed.

## 9. Evidence, confidence, and keeping skills current

**Every fact in a skill has a recorded source; low-confidence facts become questions instead of instructions.**

| Source | Meaning | Base confidence |
| --- | --- | --- |
| `RUNTIME_PROBED` | Seen on the running page by the probe | 0.90 |
| `EXTRACTED` | Stated literally in code (an attribute, a validator entry) | 0.85 |
| `CLAUDE_INFERRED` | Claude's reading of code, not stated literally | 0.60 |
| `DEVELOPER_CONFIRMED` | Answered by the developer | 1.00 |
| `USER_DEFINED` | A rule added by hand or with `add-rule` | 1.00 |

Agreeing sources combine as 1 − (1 − a)(1 − b), so code plus probe gives 0.985. Disagreeing sources cap the fact at 0.5 and raise a question. Facts at 0.7 or above go into the skill; below 0.7 they wait for the developer. A skill's `verified` metadata is `true` only when every required field was proven by the probe. Evidence (file paths, line numbers, captures) stays in `.skillgendev/` and never appears in `SKILL.md`.

### Keeping skills current

1. `skillgendev check` runs from a git hook or CI.
2. `graphify update` re-extracts only changed code files, with no LLM.
3. A route is stale when the changed files touch its slice, or touch something its slice depends on within two hops (Graphify's `affected`).
4. Only stale routes re-run the pipeline. Code facts are cached by file hash, so Claude re-reads only what changed.
5. A semantic diff names what changed: field added or removed, required flipped, options changed, dependency changed, success signal changed.
6. The skill is regenerated with its user rules untouched, its version in `metadata` bumped, and a "changed" badge in the index.

At use time, a skill that meets a page it no longer matches tells Claude to fall back to the manual path and to tell the user the skill needs regenerating.

## 10. Security

**Skills hold no credentials, and generation never writes data.**

| Risk | Control |
| --- | --- |
| Credentials in a skill | Skills contain URLs, labels, selectors and rules only. The login used for probing is a Playwright storage-state file in `.skillgendev/secrets/`, gitignored and never exported |
| Probing creates or changes data | Probing runs only against environments the developer marks as dev or staging; every non-GET request is intercepted and cancelled unless `--real-submit` is passed for a sandbox |
| Real personal data in skills | Probe captures keep body shapes, never values; examples are synthetic; `export` scans for tokens, keys, emails and phone numbers and fails when it finds any |
| Wrong environment at use time | `metadata.app-url` names the intended host; the skill tells Claude to stop if the tab is on another host and to confirm before saving on a production host |
| Destructive actions | Skills cover filling and saving forms only; delete buttons and bulk actions are never written into a skill |
| Prompt injection from page text | The skill tells Claude to treat option labels and error messages as data; `fill.js` returns them as JSON strings, truncated |
| Tampered skill folder | `export` writes `MANIFEST.sha256` with a hash of every file |
| Source code leaking to clients | Skills carry no file paths, class names or code; evidence stays internal |

Honest limit: a skill shows the client the page's field names and its route, which the client's own browser already exposes.

## 11. Libraries

**Seven dependencies cover the core; everything else is optional or a pattern we borrow.** Each row below was checked against the project's source repository on 8 Oct 2026.

### Core

| Library | Licence | What we use it for |
| --- | --- | --- |
| [Graphify](https://github.com/Graphify-Labs/graphify) (PyPI `graphifyy`) | Apache-2.0 | Code graph, page slice, change impact (`affected`), incremental `update` |
| tree-sitter + grammars | MIT | Parsing, installed with Graphify |
| Playwright for Python | Apache-2.0 | The probe: accessibility snapshot, DOM reads, request interception |
| Claude Code | Anthropic product | The analysis step: interactive, headless `claude -p --json-schema`, subagents; plugins for distribution |
| [Agent Skills spec](https://github.com/agentskills/agentskills) | Apache-2.0 (code), CC-BY-4.0 (docs) | The output format, naming rules, size guidance and evaluation method |
| [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) | Apache-2.0 | CI cross-check with `skills-ref validate`, `read-properties`, `to-prompt`. Its README says demonstration only, so our own validator is primary |
| jsonschema (Python) | MIT | Validating `page.json` and Claude's structured output |

### Optional

| Library | Licence | What for |
| --- | --- | --- |
| [ast-grep](https://github.com/ast-grep/ast-grep) | MIT | Hint packs: YAML rules that find router declarations and validation schemas in many languages; `pip install ast-grep-cli` |
| [Crawlee](https://github.com/apify/crawlee) | Apache-2.0 | Crawling very large apps for routes (Node); a simple Playwright walk covers most apps |

### Patterns we borrow (not dependencies)

| Source | Licence | What we take |
| --- | --- | --- |
| [Anthropic skills: skill-creator](https://github.com/anthropics/skills) | Apache-2.0 | `run_eval.py` (does a description trigger? via `claude -p`), `improve_description.py`, `package_skill.py`, `quick_validate.py` — the model for our verify step and description tuning |
| Anthropic skills: webapp-testing | Apache-2.0 | How to ship Playwright inside a skill; "look first, then act" |
| [Claude Code plugin layout](https://github.com/anthropics/claude-code) | — | Shipping many skills as one plugin: `.claude-plugin/plugin.json`, `skills/`, `agents/` |

### Where skills run (client side)

Claude and Cowork with their built-in browser. Nothing is installed on the client's side, and the library depends on no MCP server or browser extension.

### Graph and visuals for the index page

| Library | Licence | Role |
| --- | --- | --- |
| d3-force | ISC | Used in the demo index page: small, no build step |
| [sigma.js](https://github.com/jacomyal/sigma.js) + graphology | MIT | WebGL rendering when a real app has thousands of nodes |
| [3d-force-graph](https://github.com/vasturiano/3d-force-graph) | MIT | A 3D view for a README hero image |
| vis-network | Apache-2.0 / MIT | What Graphify's own HTML export uses (`exporters/html.py`) |

### Adjacent project

[Skill Seekers](https://github.com/yusufkaraaslan/Skill_Seekers) (MIT, `pip install skill-seekers`) turns documentation sites, repositories, PDFs and videos into **knowledge** skills about a tool. Ours turns an application into **operational** skills for its pages. It shows demand for generated skills and is a reference for packaging skills for other platforms; it is not a substitute.

## 12. Skill index page and showcase graph

**Every run writes `skills-index.html`: one page listing every skill and what it does, opening with an interactive graph of the whole app.** A working sample with demo data is published here: [Acme Admin Skill Atlas](https://claude.ai/artifact/Awg5SnMwynzM75c4njfywm).

What the page holds:

- **Header:** app name, commit, date, generator version, and the stack the tool detected (shown as proof it worked that out itself).
- **Graph:** app → routes → skills → form sections → fields, plus field dependencies (pink, with moving dots), conditions (dashed pink), lookup endpoints, shared components and the code files in each page's slice. Shared components and endpoints sit between skill clusters, which shows how pages connect. Zoom, pan, hover for details, click a node to focus its skill, search, and toggle each node type.
- **Numbers:** routes scanned, skills, fields mapped, dependencies and conditions, endpoints, code files, and the token estimate (labelled as a model until `verify` measures it).
- **Skill cards:** name with a copy button, route, title, description, field and rule counts, verified or code-only, wizard or record-id badges, sections, estimated `SKILL.md` size and calls per fill, and "Show in graph".
- **Routes without a form,** and three short "using a skill" notes.

### How it is built

- The compiler writes `skills-index.json` (nodes, links, skills) and computes the graph layout itself, then inlines both into one self-contained HTML file. The page needs no library and no network, so it works when opened from a zip on a client's laptop.
- Drawing is plain canvas, theme-aware, with node glow in dark mode. Pages with thousands of nodes switch to sigma.js (WebGL).
- `skillgendev index --png` saves a 2880×1360 screenshot of the graph through Playwright for the README.

### For GitHub

The overview at full width is the hero image; a focused skill (one cluster with its fields and dependency links labelled) is the second image, because it shows the depth up close. Run it on a real open-source app rather than the demo data so the numbers in the screenshot are true.

## 13. Repository, CLI, installation

`skillgendev` is a working name used throughout; rename it once a name is picked (section 16).

### The library's repository

```text
skillgendev/
  pyproject.toml                 # graphifyy, playwright, jsonschema; extra: astgrep
  src/skillgen/
    cli.py  workspace.py  config.py
    graph/        # Graphify adapter, page slice, change impact
    routes/       # route probes, crawl, merge into routes.json
    probe/        # fields, behaviour diff, submit interception, fill strategies
    analyze/      # prompts, page-analysis.schema.json, headless runner
    model/        # page.json schema, facts, confidence
    generate/     # SKILL.md template, fill_engine.js, index page template
    validate/     # spec checks, model checks, secret and personal-data scan
    verify/       # with-skill vs without-skill runs
    drift/        # check, semantic diff
  claude/                        # installed into Claude Code by `skillgendev install`
    commands/skillgendev.md         # the /skillgendev command
    agents/route-analyzer.md     # one route per subagent, read-only tools
    skills/skillgendev/SKILL.md     # how Claude drives the generator
  hintpacks/                     # ast-grep YAML: routers/, validators/
  tests/fixtures/                # three small apps in three different stacks
```

### What it writes into the developer's repository

```text
.skillgendev/                       # internal: never exported
  config.json  routes.json  questions.json
  pages/<skill-name>/page.json   evidence.jsonl  probe/
  rules/global.md
  secrets/                       # login session for probing; gitignored
skills/                          # public: one folder per route
  acme-individual-account/  acme-developer-kyc/  …
skills-index.html                # the index page with the graph
skills-index.json                # the same data, machine-readable
```

### CLI

```bash
skillgendev init --url http://localhost:3000     # detect stack, create .skillgendev/
skillgendev login                                 # log in once in a Playwright window; session saved for probing
skillgendev routes --all [--include "developer/*"] # find routes, write routes.json
skillgendev generate --route /developer/kyc       # one route
skillgendev generate --all [--concurrency 4] [--code-only]
skillgendev answer <question-id> "<answer>"
skillgendev add-rule acme-developer-kyc "Only allow names starting with A" [--global]
skillgendev verify --all                          # with vs without skill, on dev
skillgendev index                                 # rebuild skills-index.html
skillgendev check [--since HEAD~1]                # what changed, regenerate stale routes
skillgendev export [--zip] [--plugin]             # skills only; plugin = one Claude Code plugin per app
skillgendev install                               # add /skillgendev, the subagent and the driver skill to Claude Code
```

Inside Claude Code most developers will type `/skillgendev /developer/kyc` or `/skillgendev all` and never call the CLI directly.

### Installation

- **Developer:** `uv tool install skillgendev` (or `pipx install skillgendev`). Graphify and its grammars arrive as normal dependencies; `skillgendev doctor --fix` downloads Playwright's Chromium. The analysis step uses the developer's Claude Code; an `--analyzer api` mode with an API key is for CI.
- **Anyone receiving skills:** copy the skill folders into `~/.claude/skills/` (personal) or the project's `.claude/skills/`, or install the exported plugin. Needs only Claude or Cowork with its built-in browser.

## 14. Failure modes and fallbacks

**Most hard cases are handled by the probe proving a strategy, or by the skill handing one step to the user; none needs framework-specific code.**

| Case | Handling |
| --- | --- |
| No running app available | Code-only mode; skill marked `verified: false`; probe later to upgrade |
| Routes built at runtime or by a CMS | Runtime crawl, or `--route` given by hand |
| Widget with no accessibility role (canvas, map, drag and drop) | Claude reads its code and writes short steps; kept only if the probe proves them. Otherwise the skill tells Claude to ask the user to do that one field |
| Third-party dropdowns, date pickers, tree pickers | Covered by `aria-combobox`, `native-input` and `aria-tree` strategies in most cases; `steps` otherwise |
| Rich-text editors | `rich-text` strategy; embedded media left to the user |
| File uploads | Browser tool's upload action with a file the user supplies |
| Multi-step wizards | One skill for the flow when the probe sees the steps stay inside it; resumable step by step |
| Behaviour only in frontend code | Handled by design: the fill goes through the page, so the app's own code runs |
| Rules that exist only in people's heads | Developer adds them with `add-rule`; Claude asks the user at fill time |
| Server-only validation ("must be unique") | Listed in the skill as server-checked; `__submit` returns the server's message |
| Permission-dependent fields | Probe records what the probing user sees; the skill notes fields that may be hidden for some roles |
| CAPTCHA, 2FA, login walls | Always handed to the user |
| Script evaluation blocked by the page | The skill's "Without JavaScript" path |
| App changed since the skill was generated | Runtime falls back to the manual path and says the skill is stale; `skillgendev check` regenerates it |
| Non-web apps (desktop, mobile) | Out of scope for v1 |

## 15. Build plan

**MVP in 8 weeks for one developer, tested from week 1 on three apps in three different stacks** (the client app plus two open-source apps), so framework-agnosticism is proven rather than assumed.

| Week | Build | Exit test |
| --- | --- | --- |
| 1 | Workspace, Graphify adapter, page slice | On all 3 apps, slices contain the files a developer would name for 5 pages each |
| 2 | Route discovery: folder routing, 3 router hint packs, crawl, Claude fallback, naming | At least 90% of real routes found; names pass the spec |
| 3 | Probe I: fields from the accessibility tree and DOM, selectors, sections | At least 95% of visible fields found, every selector unique |
| 4 | Probe II: behaviour diff, submit interception, fill strategies | Conditions and dependency chains detected; zero records created |
| 5 | Analyze: prompt, JSON schema, headless runner, subagent; merge, confidence, questions | Under 10 questions per 50-field page; 95% of facts confirmed by a developer |
| 6 | Generate: `SKILL.md` template, `fill.js`, references split, validators, scan | Every skill passes spec checks and `skills-ref validate`; one-call fill works on every probed page |
| 7 | Index page and graph, `add-rule`, export (zip and plugin), `install` | A teammate installs one skill from the zip and fills its page |
| 8 | Verify and measure (with vs without skill on 5 pages), basic `check` | Measured token reduction of at least 5x, published in the README |

**Phase 2:** semantic drift diff and CI mode; more hint packs; probing per user role for permission-dependent fields; read-only skills for list and detail pages; multi-language labels.

**Phase 3:** test the same skills in Codex, Cursor and Gemini CLI (already spec-compatible); bulk fills from a CSV; a hosted gallery of example skills.

### First tasks

- [ ] Pick the name (section 16) and reserve the GitHub organisation, PyPI and npm names
- [ ] Run Graphify on the client repository and check the slice for three pages by hand
- [ ] Choose two open-source test apps in other stacks
- [ ] Write `page.json` schema v1 and the `SKILL.md` template from section 6
- [ ] Spike `fill.js` on the hardest widget in the client app

## 16. Names

**Recommendation: Formcast, with Skillmint as runner-up.** Neither turned up an existing project in web searches; PyPI, npm and GitHub search were not reachable from my workspace, so check those three and a trademark search before committing.

### Why "Graphify" works

- **It names the result, not the input.** Graphify takes code, docs, papers, images and video, so a name like "CodeGraph" would have been too narrow. "Graph" + "-ify" means "turn it into a graph", whatever "it" is.
- **It is a verb.** You can say "graphify this repo", and the slash command `/graphify` reads like an instruction.
- **It borrows a famous pattern.** "-ify" names (Spotify, Shopify) feel like products and are easy to remember and spell.
- **It is short and sayable**, with no explanation needed once you know the output.

So the same test for our name: does it name what comes out (a page skill) or the act of making it, and does it read well as a verb and as `/name`?

| Name | Idea | In a sentence | Collision check (web search, 8 Oct 2026) | Verdict |
| --- | --- | --- | --- | --- |
| **Formcast** | Cast the code into a form skill, like a mould taken from the original | "formcast the KYC page" | Nothing found | **Top pick** |
| **Skillmint** | Mint a new skill from code | "skillmint every route" | Nothing found | **Runner-up**; broader if you go beyond forms |
| Skilldown | Skill + markdown: write it down once | "skilldown the app" | Nothing found | Good, playful |
| Skillery | A place where skills are made (bakery, brewery) | "run it through Skillery" | Nothing found | Good |
| Pagelore | The knowledge of each page | "pagelore /developer/kyc" | Nothing found | Good |
| Formlore | The knowledge of each form | "formlore the signup page" | Nothing found | Good |
| Routelore | The knowledge of each route | "routelore --all" | Nothing found | Good, longer |
| Routeskill | Literal: a skill per route | "routeskill --all" | "SkillRoute" exists on PyPI | Usable, weaker |
| Skillify | The exact Graphify analogue | "skillify your app" | Several existing agent skills are already called skillify | Avoid: would clash as a skill name |
| Formify | Turn pages into form knowledge | — | Several npm and GitHub form libraries | Avoid |
| Fieldify | Turn fields into knowledge | — | A Shopify app and an npm scope | Avoid |
| Fillify | Make anything fillable | — | An existing "AI form filler" Chrome extension | Avoid: same space |
| Formwise | Wise about forms | — | formwise.ai exists | Avoid |
| Skillgraph | Graph of skills | — | Several tools use it | Avoid |
| Skillprint | Blueprint of skills | — | A company uses it | Avoid |

Formcast reads naturally in every place the name appears: `pip install formcast`, `/formcast /developer/kyc`, `formcast routes --all`, and "generated by Formcast" in each skill's metadata.

## 17. Sources

Repositories read at source (cloned 7–8 Oct 2026):

- [Graphify](https://github.com/Graphify-Labs/graphify) — `ARCHITECTURE.md`, `pyproject.toml`, `extract.py` (`extract_vue`), `affected.py`, `watch.py`, `serve.py`, `exporters/html.py`
- [Agent Skills](https://github.com/agentskills/agentskills) — `docs/specification.mdx`, `docs/skill-creation/best-practices.mdx`, `evaluating-skills.mdx`, `docs/snippets/clients.jsx`, `skills-ref/`
- [Anthropic skills](https://github.com/anthropics/skills) — `skills/skill-creator/scripts/`, `skills/webapp-testing/`
- [Claude Code](https://github.com/anthropics/claude-code) — `CHANGELOG.md` (headless `claude -p`, `--json-schema`), `plugins/plugin-dev/skills/`, `plugins/feature-dev/agents/`
- [Playwright MCP](https://github.com/microsoft/playwright-mcp) — README tool list
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) — `docs/tool-reference.md`
- [ast-grep](https://github.com/ast-grep/ast-grep), [Crawlee](https://github.com/apify/crawlee), [sigma.js](https://github.com/jacomyal/sigma.js), [3d-force-graph](https://github.com/vasturiano/3d-force-graph), [Skill Seekers](https://github.com/yusufkaraaslan/Skill_Seekers) — READMEs and licences

Name checks (web search, 8 Oct 2026):

- Skillify: [kk-r/skillify-skill](https://github.com/kk-r/skillify-skill), [garrytan skillify](https://www.typingmind.com/skills/garrytan-skillify)
- Formify: [formify-js on npm](https://npmjs.com/package/formify-js), [Basharath/Formify](https://github.com/Basharath/Formify)
- Fieldify: [Fieldify on the Shopify App Store](https://apps.shopify.com/fieldify), [@fieldify/antd](https://www.npmjs.com/package/@fieldify/antd)
- Fillify: [Fillify Chrome extension](https://chrome.google.com/webstore/detail/fillify/mhhcjilkgnegleamofnbeacpnblblkhn)
- Formwise: [formwise.ai](https://www.formwise.ai/blog/what-are-smartforms-in-formwise-the-easiest-way-to-build-fill-in-the-blank-gpt-tools)
- Skillprint: [Skillprint on Dealroom](https://datacommons.dealroom.co/companies/skillprint)
- SkillRoute: [skillroute on PyPI](https://pypi.org/project/skillroute/)

Not verified here: PyPI, npm and GitHub search could not be reached from my workspace, and the Claude Code docs site needed a permission no one was present to approve, so Claude Code facts come from Anthropic's public `claude-code` repository instead.
