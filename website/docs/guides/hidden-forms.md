---
title: Hidden forms and views
description: Wizards, tabs, dialogs and forms behind a button, described from the code and walked by one script.
---

# Hidden forms and views

Many forms do not show every field at once: a multi-step form shows one step at a time,
tabs show one panel, a dialog opens with a button, and some fields appear only for one
choice. skillgendev handles all of them the same way, from your code.

## Views

1. **Claude reads the code** (the Graphify code map gives it the page's files) and lists
   every hidden part as a **view**: its name, the click that reaches it from the part before,
   and the fields it shows. Fields that appear for a value (*Video length* only when *Format* is
   *Video*) are recorded as conditions, not views.
2. **`--xy` walks every view in Chromium.** For each one it opens the page fresh, makes the
   clicks with the same script the skill uses, fills earlier parts with safe made-up values
   (so a *Next* that checks the step lets it through), waits for the fields to appear, and
   measures them. A conditional field is shown by setting the field it depends on.
3. **The skill walks them too.** One call fills every step: it opens a part only when a value
   belongs there, checks its fields appeared, fills them, closes a dialog with its *Done*
   button, and stops before *Submit*. If the page refuses to move on (a required field is
   missing), it stops and reports the page's own error messages.

Nothing is ever submitted while walking, and a click such as *Save* or *Delete* is never
made. A view Claude only deduced, rather than read plainly in the code, is used once its
fields really appeared.

**Example.** A campaign wizard with two tabs on step 1 and four steps:

| View | Click | Fields |
| --- | --- | --- |
| Audience tab | "Audience" | country, region, interests |
| Schedule tab | "Schedule" | start date, end date |
| Step 2: Creative | "Next" | headline, ad copy, video length (for video ads) |
| Step 3: Budget | "Next" | daily budget, bid strategy |
| Step 4: Review | "Next" | agree to the advertising policy |

With `--xy`, every field of every step gets x/y, and `references/layout.json` says which view
each was measured in. Claude decides what to click by reading the code; skillgendev does the
clicking with one tested script, in Chromium while generating and in the filling AI's own
browser later. No new code is written per page.

## `--open`: when the form is hidden behind a button {#open-when-the-form-is-hidden-behind-a-button}

Some pages do not show their form straight away. You click a **Targeting** button, a tab or
an **Edit campaign** link first. skillgendev cannot measure fields it cannot see, so it has to make that
click.

**Usually skillgendev finds the click itself.** Claude records what opens the form while it
reads the page's code, `--xy` makes that click and checks that the fields appear, and the
skill makes the same click when it fills the page.

If Claude only guessed the click, or the click could change data (such as **Save** or
**Delete**), skillgendev does not use it. It asks you first in `skillgendev questions`. Answer
`yes`, or give the right click; separate several with `;`:

```bash
skillgendev answer q1a2b3c "text:Audience settings"
```

**`--open` sets the click yourself.** Use it when skillgendev did not find the click, or found
the wrong one. Your `--open` always wins over the code analysis.

```bash
skillgendev generate --route /campaigns/42/edit --name campaign-edit --xy --open "text:Audience settings"
```

### How to say what to click

| You write | It clicks |
| --- | --- |
| `--open "text:Audience settings"` | the button, link or tab whose text, or tooltip, is exactly *Audience settings* |
| `--open "#settings-button"` | the element this CSS selector finds |

Prefer `text:`. It is easier to read and works in every terminal. In Windows PowerShell, a
CSS selector with quotes inside it, such as `button[title="Audience settings"]`, loses those
quotes.

**Several clicks.** Repeat `--open`, in the order you would click:

```bash
skillgendev generate --route /ads/manager --name ad-budget --xy --open "text:Ad sets" --open "text:Edit budget"
```

**You type it once.** skillgendev saves it for that route in `.skillgendev/routes.json` as `"open"`,
and keeps it when routes are found again. Next time `--xy` is enough. To change it, run
`--open` again or edit `"open"` in `routes.json`.

At fill time the skill clicks the open steps **only while the form is closed**: it checks
whether the form's first steady field is visible, because an open step is often a toggle
and a second click would close the panel again.
