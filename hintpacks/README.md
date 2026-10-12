# Hint packs

Hint packs are the only place framework knowledge lives. They are YAML data, read by
generic code; deleting this folder leaves a working tool that finds routes through the
other sources (your `--route`, the runtime crawl, Claude Code).

Every pack has an `id`, a `kind` and a short `about`. Three kinds exist.

## `kind: folder` — folder-based routing

```yaml
id: nextjs-app
kind: folder
about: Next.js app router (app/**/page.tsx)
roots: [app, src/app]            # folders to scan, relative to each project root
requires_any: [next.config.js, package.json]  # files that mark a project root
page_files: ["page.{tsx,jsx,ts,js,mdx}"]   # file names that make a folder a page
route_from: folder               # folder: route is the folder path; file: route is the file path
index_names: [index]             # with route_from: file, these names map to their folder
skip_segments: ["^\\(.*\\)$", "^@"]       # path parts dropped from the route (groups, slots)
skip_files: ["^_", "^api$"]      # path parts that make the whole file not a page
params:                          # how parameter segments are written → :name
  - "^\\[\\[?\\.\\.\\.(?P<name>\\w+)\\]?\\]$"
  - "^\\[(?P<name>\\w+)\\]$"
```

`requires_any` lets one repository hold several apps. Every folder that holds one
of these files, at any depth, is a project root, and `roots` is looked for inside
each. In a monorepo with `admin/next.config.js` and `site/package.json`, both
`admin/src/app` and `site/app` are scanned. Dependency and build folders
(`node_modules`, `dist`, hidden folders) are never searched. Without `requires_any`
the pack applies at the repository root only.

## `kind: router` — route declarations found with ast-grep

```yaml
id: react-router-jsx
kind: router
about: <Route path="/x" element={<Page />} />
language: tsx
globs: ["**/*.tsx", "**/*.jsx"]
rule:                            # any ast-grep rule
  pattern: <Route path=$PATH element={<$COMPONENT $$$ />} $$$ />
captures:
  path: PATH                     # metavariable holding the route path (a string literal)
  component: COMPONENT           # optional: metavariable naming the page component
prefix_from: none                # reserved for nested routers
```

The component name is resolved to a file through the code graph, so packs never
describe import syntax. When the captured text is not a plain name (Rails writes
`"registrations#new"`), two optional keys reshape it:

```yaml
component_match: "^[\"']?(?P<name>[\\w/]+)#"   # regex with a `name` group
component_format: "{pascal}Controller"           # {name} or {pascal}: registrations → RegistrationsController
```

Shipped router packs: React Router, route objects, Express, Flask, Django, Laravel,
Rails, Spring MVC, ASP.NET Core attributes and Phoenix. Each has a tiny sample app under
`tests/fixtures/hintpacks/<id>/` or `tests/fixtures/<app>/`.

When no pack matches, skillgendev asks Claude Code to read the code graph's likely router
files (`skillgendev routes --all --ask-claude`), so a missing pack never blocks anyone.

## `kind: validator` — field constraints found with ast-grep

```yaml
id: zod-string-min
kind: validator
about: z.string().min(n) inside an object schema
language: typescript
rule: { pattern: "$FIELD: z.string().min($MIN)" }
captures: { field: FIELD, min_length: MIN }
```

Validator packs only add `EXTRACTED` facts that Claude Code would otherwise read
itself; they make analysis cheaper, never required.

## Adding a pack

1. Add the YAML file here.
2. Add a tiny example under `tests/fixtures/hintpacks/<id>/` and a case in
   `tests/test_hintpacks.py`.
3. Run `uv run pytest tests/test_hintpacks.py`.
