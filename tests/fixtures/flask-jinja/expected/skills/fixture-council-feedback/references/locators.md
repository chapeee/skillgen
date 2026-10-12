# Give feedback — locators

For a browser tool that acts on elements by role, name or selector instead of running page scripts: `fill()`, `selectOption()`, `check()` and `click()` in Playwright's words, or the same actions under other names. Take values from the user; the options are in SKILL.md's field table.

Find each field by its role and name (`getByRole(role, { name })`, or `getByLabel(name)` when the role is empty). If that finds nothing or several elements, use its CSS selector. Work in this order, and read each value back before submitting.

| Key | Role | Name | CSS | Do | When |
|---|---|---|---|---|---|
| `department` | combobox | Department | `#department` | `selectOption({ label: value })` |  |
| `subject` | textbox | Subject | `#subject` | `fill(value)` |  |
| `rating` | radio | each option's label | `input[name=rating]` | `check()` the option whose label is the value |  |
| `details` | textbox | Details | `#details` | `fill(value)` |  |
| `contact_me` | checkbox | Contact me about this | `#contact_me` | `check()` for yes, `uncheck()` for no |  |
| `email` | textbox | Email | `#email` | `fill(value)` |  |

## Submit
Click "Send feedback" (`button[type=submit]`) only when every field is done, as SKILL.md says under "Submit and verify".
