# Profile — locators

For a browser tool that acts on elements by role, name or selector instead of running page scripts: `fill()`, `selectOption()`, `check()` and `click()` in Playwright's words, or the same actions under other names. Take values from the user; the options are in SKILL.md's field table.

Find each field by its role and name (`getByRole(role, { name })`, or `getByLabel(name)` when the role is empty). If that finds nothing or several elements, use its CSS selector. Work in this order, and read each value back before submitting.

| Key | Role | Name | CSS | Do | When |
|---|---|---|---|---|---|
| `display_name` | textbox | Display name | `[data-testid=field-display_name]` | `fill(value)` |  |
| `job_title` | textbox | Job title | `[data-testid=field-job_title]` | `fill(value)` |  |
| `bio` | textbox | About you | `#bio` | `fill(value)` |  |
| `theme` | radio | each option's label | `input[name=theme]` | `check()` the option whose label is the value |  |

## Submit
Click "Save profile" (`button[type=submit]`) only when every field is done, as SKILL.md says under "Submit and verify".
