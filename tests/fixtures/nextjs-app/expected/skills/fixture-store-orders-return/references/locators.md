# Return items — locators

For a browser tool that acts on elements by role, name or selector instead of running page scripts: `fill()`, `selectOption()`, `check()` and `click()` in Playwright's words, or the same actions under other names. Take values from the user; the options are in SKILL.md's field table.

Find each field by its role and name (`getByRole(role, { name })`, or `getByLabel(name)` when the role is empty). If that finds nothing or several elements, use its CSS selector. Work in this order, and read each value back before submitting.

| Key | Role | Name | CSS | Do | When |
|---|---|---|---|---|---|
| `reason` | radio | each option's label | `input[name=reason]` | `check()` the option whose label is the value |  |
| `items[].sku` | textbox | SKU | `input[data-field=sku]` | `fill(value)` | in each Item row |
| `items[].quantity` | spinbutton | Quantity | `input[data-field=quantity]` | `fill(value)` | in each Item row |
| `refund_method` | combobox | Refund to | `select[name=refund_method]` | `selectOption({ label: value })` |  |

## Repeating rows
- `items` (Item): each row matches `.item-row`; in row n, look for the field's CSS inside the n-th match. Add a row with `button[type=button]`. At least 1 row(s) are needed.

## Submit
Click "Request return" (`button[type=submit]`) only when every field is done, as SKILL.md says under "Submit and verify".
