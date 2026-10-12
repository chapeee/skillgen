# Test bench: check skills end to end in Claude and Cowork

One page with every kind of form widget skillgendev supports, the skill skillgendev
generates for it, and fourteen test cases. Use it to check that a change to skillgendev
still produces skills that Claude and Cowork can use, and to compare runs.

Everything here is synthetic. The countries, cities and people do not exist.

```text
tests/bench/
  site/                    the bench page (plain HTML + JS that behaves like a framework app)
  serve.py                 serves the page and a small fake API (Python standard library only)
  page.json                the page model the skill is generated from
  skills/bench-apply/      the generated skill (SKILL.md, scripts/fill.js, evals/)
  cases.json               the test cases: prompt, follow-up answer, expected submission
  check.py                 list cases, print prompts, reset the server, check results
  files/sample-id.pdf      a synthetic file for the upload case
```

## What the page covers

| Widget | Field | Strategy in the skill |
| --- | --- | --- |
| Text, email, date, textarea | Full name, Email, Username, Date of birth, Short bio | `native-input` |
| Radio group | Account type | `choice` |
| Fields that appear on a condition | Company name, Registration number, Team size | `native-input`, `native-select` |
| Select | Country, Team size | `native-select` |
| Select whose options load after another field | Region (after Country, from the server) | `native-select` |
| Searchable dropdown | City (server search, two "Springfield"s, one label with instructions in it) | `aria-combobox` |
| Checkbox group | Interests | `choice` |
| Tree picker, rendered lazily | Department | `aria-tree` |
| Chips (multi-select listbox) | Skills | `aria-listbox` |
| Single checkbox | Newsletter, Declaration | `native-input` |
| Rich-text editor | Statement | `rich-text` |
| Repeatable rows | References (name, email) | rows under `references` |
| File upload | Identity document | `file` (browser upload action) |
| Server-side validation | Username "taken", "admin" or "root" is rejected with 422 | `__submit` returns errors |
| Disabled submit | Submit stays disabled until the declaration is ticked | gotcha in SKILL.md |

The page keeps its values in a state object that only changes on input, change and
click events, like React, Vue or Angular. A fill that sets `.value` without firing
events is not saved, so the bench catches that bug too.

## 1. Start the bench

```bash
python3 tests/bench/serve.py          # http://localhost:8765/apply
```

Open http://localhost:8765/apply once yourself to check that it loads. The browser
Claude uses must be able to reach `localhost`, so run this on the same computer as
Claude in Chrome or the Claude desktop app.

## 2. Add the skill to Claude or Cowork

- **Claude and Cowork (claude.ai or the desktop app):** build the zip with
  `python3 tests/bench/check.py zip`, then upload `tests/bench/dist/bench-apply.zip`
  in Claude's Skills settings.
- **Claude Code:** `python3 tests/bench/check.py install` copies the skill to
  `~/.claude/skills/bench-apply/`.

Nothing else is needed: no MCP server, no extension beyond the browser Claude already
uses, no API key.

## 3. Run a case

```bash
python3 tests/bench/check.py list         # all cases
python3 tests/bench/check.py prompt 01    # the prompt, the follow-up, what to look for
python3 tests/bench/check.py reset        # clear earlier submissions
```

Paste the prompt into a new Claude or Cowork conversation. When Claude asks a
question, reply with the case's follow-up answer. Then:

```bash
python3 tests/bench/check.py check 01     # PASS or FAIL, with the differences
```

`check` compares what the server received with the case. Also judge by hand whether
Claude did what the case lists under "should" and avoided "should not": for example,
that it asked once instead of three times, or did not follow text inside an option
label.

## The cases

| Id | What it checks |
| --- | --- |
| 01-happy-path | Every value given: one fill call, one submit |
| 02-company-conditional | Conditional fields appear and are filled |
| 03-missing-required | Claude asks once for every missing value, then finishes |
| 04-dependent-options | Region waits for its server-loaded list |
| 05-ambiguous-option | Two cities match: Claude asks which |
| 06-not-an-option | An unknown country: Claude lists the real choices, invents nothing |
| 07-client-rule | A value breaking a rule: Claude explains and asks |
| 08-server-rejection | Server rejects the username: Claude fixes only that field |
| 09-tree-chips-checkboxes | Tree path, chips and a checkbox group |
| 10-rows-and-rich-text | Three reference rows and a longer statement |
| 11-page-text-is-data | An option label with instructions inside is treated as data |
| 12-file-upload | Upload through the browser's upload action (attach the sample PDF) |
| 13-without-javascript | No scripts: fill by label from the table |
| 14-wrong-host | Page on 127.0.0.1 instead of localhost: Claude stops |

## What one fill costs

Measured on this bench skill, 2026-10-08, counting the text that reaches a reader.

| | before | inline setter | with layout check |
| --- | ---: | ---: | ---: |
| Read `SKILL.md` | 1,547 | 3,059 | 3,761 |
| Read `scripts/fill.js` | 4,661 | 0 | 0 |
| Pass the script to `javascript_tool` | 4,661 | 1,394 | 1,946 |
| **One fill** | **10,869** | **4,453** | **5,707** |
| Each later fill with more values | about 20 | about 53 | about 53 |

The original `fill.js` stayed loaded in the page, so later fills were already cheap;
the first version of the inline setter lost that by resending its whole block, and
keeping the setter loaded restores it. The inline setter column includes that and
`locate`, which this page needs for its file field. The layout check costs about 1,250
more per fill; what it buys is that a changed or covered page is never written to.

The bench's layout was captured by running the real `probe/extract.js` in Chromium at
1280x900; see `docs/decisions.md`. To check the layout states by hand, open the bench
and run the `SKILL.md` block at 1280 wide (`match`), at another width (`resized`), with
a dialog over the form (`blocked`) and with a field removed (`changed`).

Regenerate these numbers after changing the setter or the engine, and update the
table in the same commit.

## Results template for pull requests

Copy this into your pull request when your change affects generated skills.

```markdown
| Case | Claude (Chrome) | Cowork | Notes |
| --- | --- | --- | --- |
| 01-happy-path | PASS | PASS | |
| 03-missing-required | PASS | PASS | asked once |
| … | | | |

Client versions: …    skillgendev commit: …
```

## Automated checks (no Claude needed)

`uv run pytest tests/test_bench.py` checks that the committed skill matches what
skillgendev generates today, and that it passes the spec checks and the secret scan.
`uv run pytest -m browser tests/test_bench.py` replays every case's `fill` values
through `scripts/fill.js` in Chromium against a local bench server, including the
follow-ups, the server rejection and the wrong-host guard. These tests prove the
script works; the manual runs above prove Claude uses the skill well.

After changing the generator or `page.json`, regenerate the committed skill with
`uv run pytest tests/test_bench.py --update-golden` and review the diff.
