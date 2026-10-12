# Edit project — locators

For a browser tool that acts on elements by role, name or selector instead of running page scripts: `fill()`, `selectOption()`, `check()` and `click()` in Playwright's words, or the same actions under other names. Take values from the user; the options are in SKILL.md's field table.

Find each field by its role and name (`getByRole(role, { name })`, or `getByLabel(name)` when the role is empty). If that finds nothing or several elements, use its CSS selector. Work in this order, and read each value back before submitting.

| Key | Role | Name | CSS | Do | When |
|---|---|---|---|---|---|
| `project_name` | textbox | Project name | `[data-testid=field-project_name]` | `fill(value)` |  |
| `status` | combobox | Status | `#status` | `selectOption({ label: value })` |  |
| `due_date` |  | Due date | `[data-testid=field-due_date]` | `fill(value)` |  |

## Submit
Click "Save changes" (`button[type=submit]`) only when every field is done, as SKILL.md says under "Submit and verify".
