# Bench application — locators

For a browser tool that acts on elements by role, name or selector instead of running page scripts: `fill()`, `selectOption()`, `check()` and `click()` in Playwright's words, or the same actions under other names. Take values from the user; the options are in SKILL.md's field table.

Find each field by its role and name (`getByRole(role, { name })`, or `getByLabel(name)` when the role is empty). If that finds nothing or several elements, use its CSS selector. Work in this order, and read each value back before submitting.

| Key | Role | Name | CSS | Do | When |
|---|---|---|---|---|---|
| `full_name` | textbox | Full name | `#full_name` | `fill(value)` |  |
| `email` | textbox | Email | `#email` | `fill(value)` |  |
| `username` | textbox | Username | `#username` | `fill(value)` |  |
| `birth_date` |  | Date of birth | `#birth_date` | `fill(value)` |  |
| `bio` | textbox | Short bio | `#bio` | `fill(value)` |  |
| `account_type` | radio | each option's label | `input[name="account_type"]` | `check()` the option whose label is the value |  |
| `company_name` | textbox | Company name | `#company_name` | `fill(value)` | only when Account type is Company |
| `registration_no` | textbox | Registration number | `#registration_no` | `fill(value)` | only when Account type is Company |
| `team_size` | combobox | Team size | `#team_size` | `selectOption({ label: value })` | only when Account type is Company |
| `country` | combobox | Country | `#country` | `selectOption({ label: value })` |  |
| `region` | combobox | Region | `#region` | `selectOption({ label: value })` | after Country |
| `city` | combobox | City | `#city` | `fill(value)`, wait for the list, then `click()` the option with that text |  |
| `interests` | checkbox | each option's label | `input[name="interests"]` | `check()` each wanted option, found by its label |  |
| `department` | tree | Department | `#department` | `click()` each level of the path, split at "/", in order |  |
| `skills` | listbox | Skills | `#skills` | `click()` to open it, then `click()` each wanted option by text |  |
| `newsletter` | checkbox | Send me the newsletter | `#newsletter` | `check()` for yes, `uncheck()` for no |  |
| `statement` | textbox | Why are you applying? | `#statement` | `click()`, then type the text |  |
| `references[].name` | textbox | Reference name | `input[data-field=name]` | `fill(value)` | in each Reference row |
| `references[].email` | textbox | Reference email | `input[data-field=email]` | `fill(value)` | in each Reference row |
| `id_document` |  | Identity document (PDF or JPG, up to 2 MB) | `#id_document` | `setInputFiles()` with the file the user gives |  |
| `agree_terms` | checkbox | I confirm the details above are correct | `#agree_terms` | `check()` for yes, `uncheck()` for no |  |

## Repeating rows
- `references` (Reference): each row matches `.reference-row`; in row n, look for the field's CSS inside the n-th match. Add a row with `#add-reference`. At least 1 row(s) are needed.

## Submit
Click "Submit application" (`#submit`) only when every field is done, as SKILL.md says under "Submit and verify".
