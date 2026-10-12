---
title: Questions and rules
description: Confirm uncertain facts with questions and answer, and add your own page or global rules with optional machine checks.
---

# Questions and rules

## Questions

Some facts in your code are unclear: Claude deduced them rather than read them, or the code
and the live page disagree. Facts below a confidence of 0.7 stay out of the skill and become
questions for you (see [The page model](../concepts/page-model.md#confidence)).

```bash
skillgendev questions                    # open questions
skillgendev questions --skill new-campaign  # one skill
skillgendev questions --all              # include answered ones
```

Each question has an id, the skill, the subject (such as a field's `required`), the text and
any suggested choices. Questions are stored in `.skillgendev/questions.json`.

### Answering

```bash
skillgendev answer q1a2b3c yes
skillgendev generate --route /campaigns/new --overwrite
```

An answer applies on the next `generate`. Because the skill exists, that needs
`--overwrite`. The analysis is reused, so it costs no tokens.

| Answer | Effect |
| --- | --- |
| `yes`, `y`, `true`, `keep`, `confirm`, `correct`, `code` | Keep the value the code claimed |
| `no`, `n`, `false`, `drop`, `remove`, `wrong` | Drop the fact |
| `page`, `probe` | Use the value the probe saw on the page (when there is one) |
| anything else | Use your text as the value |

A confirmed answer becomes a `DEVELOPER_CONFIRMED` fact with confidence 1.0. Answers given
to the same subject are kept across regenerations.

## Page rules

Rules that exist only in people's heads can be added to a skill:

```bash
skillgendev add-rule new-campaign "Daily budget must be at least 10" --check "daily_budget min 10"
```

`add-rule` appends the rule to `SKILL.md` straight away, between the user markers, where it
survives every regeneration. Its check reaches the fill script when you regenerate the
skill (it already exists, so pass `--overwrite`):

```bash
skillgendev generate --route new-campaign --overwrite
```

The block looks like this:

```markdown
## Rules
<!-- skillgendev:generated -->
- The end date must be after the start date.
<!-- skillgendev:user:start -->
- Daily budget must be at least 10.  `check: daily_budget min 10`
<!-- skillgendev:user:end -->
```

You can also edit that block by hand. Anything between the markers is kept as is.

### Machine checks

A rule line may carry a check in backticks, which is compiled into the fill script, so the
value is checked before it is filled:

| Check | Meaning |
| --- | --- |
| `` `check: utm_campaign ^[a-z0-9_]+$` `` | The value matches the regular expression `^[a-z0-9_]+$` |
| `` `check: daily_budget min 10` `` | A number of at least 10 |
| `` `check: bid_cap max 50` `` | A number of at most 50 |
| `` `check: promo_code length 4..8` `` | Between 4 and 8 characters |
| `` `check: report_date not-future` `` | A date that is not in the future |

The key is the field's key from the skill's field table. A check that names no condition,
has a bad number, or holds an invalid regular expression is refused with an error.

:::note
By design, a rule should only add constraints to what the app already enforces. Write
rules that narrow what is accepted; skillgendev does not check today whether a rule loosens
one of the app's own rules.
:::

## Global rules

```bash
skillgendev add-rule "Never launch a campaign without a UTM tag" --global
```

Global rules are kept once in `.skillgendev/rules/global.md` and copied into every skill's rules
at generate time, under "Rules for all pages". Regenerate your skills (with `--overwrite`) to
copy a new global rule in. Copying is deliberate: each skill must work when it is shared
alone.
