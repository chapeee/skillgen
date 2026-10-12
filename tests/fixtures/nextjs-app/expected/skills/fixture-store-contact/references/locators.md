# Contact us — locators

For a browser tool that acts on elements by role, name or selector instead of running page scripts: `fill()`, `selectOption()`, `check()` and `click()` in Playwright's words, or the same actions under other names. Take values from the user; the options are in SKILL.md's field table.

Find each field by its role and name (`getByRole(role, { name })`, or `getByLabel(name)` when the role is empty). If that finds nothing or several elements, use its CSS selector. Work in this order, and read each value back before submitting.

| Key | Role | Name | CSS | Do | When |
|---|---|---|---|---|---|
| `name` | textbox | Your name | `input[name=name]` | `fill(value)` |  |
| `email` | textbox | Email | `input[name=email]` | `fill(value)` |  |
| `topic` | combobox | Topic | `select[name=topic]` | `selectOption({ label: value })` |  |
| `order_number` | textbox | Order number | `input[name=order_number]` | `fill(value)` | only when Topic is Billing |
| `message` | textbox | Message | `textarea[name=message]` | `fill(value)` |  |

## Submit
Click "Send message" (`button[type=submit]`) only when every field is done, as SKILL.md says under "Submit and verify".
