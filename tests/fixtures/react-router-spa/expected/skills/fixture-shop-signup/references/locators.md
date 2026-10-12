# Create your account — locators

For a browser tool that acts on elements by role, name or selector instead of running page scripts: `fill()`, `selectOption()`, `check()` and `click()` in Playwright's words, or the same actions under other names. Take values from the user; the options are in SKILL.md's field table.

Find each field by its role and name (`getByRole(role, { name })`, or `getByLabel(name)` when the role is empty). If that finds nothing or several elements, use its CSS selector. Work in this order, and read each value back before submitting.

| Key | Role | Name | CSS | Do | When |
|---|---|---|---|---|---|
| `full_name` | textbox | Full name | `[data-testid=field-full_name]` | `fill(value)` |  |
| `work_email` | textbox | Work email | `[data-testid=field-work_email]` | `fill(value)` |  |
| `password` |  | Password | `[data-testid=field-password]` | ask the user to set it by hand |  |
| `plan` | combobox | Plan | `#plan` | `selectOption({ label: value })` |  |
| `seats` | spinbutton | Number of seats | `[data-testid=field-seats]` | `fill(value)` | only when Plan is Enterprise |
| `accept_terms` | checkbox | I accept the terms | `[name=accept_terms]` | `check()` for yes, `uncheck()` for no |  |

## Submit
Click "Create account" (`button[type=submit]`) only when every field is done, as SKILL.md says under "Submit and verify".
