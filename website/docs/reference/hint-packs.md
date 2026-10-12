---
title: Hint packs
description: The YAML format for folder-routing and router hint packs, the only place framework knowledge lives.
---

# Hint packs

Hint packs are the only place framework knowledge lives. They are YAML data read by generic
code; deleting the `hintpacks/` folder leaves a working tool that finds routes through the
other sources (your `--route`, Graphify, Claude Code).

Every pack has an `id`, a `kind` and a short `about`. skillgendev loads every `*.yml` under the
shipped `hintpacks/` folder (packaged inside the wheel), then under any folders listed in
`config.json` `hintpacks`.

## Shipped packs

| Kind | Packs |
| --- | --- |
| `folder` | `nextjs-app`, `nextjs-pages`, `nuxt-pages`, `sveltekit-routes`, `astro-pages` |
| `router` | `react-router-jsx`, `route-objects`, `route-objects-js`, `express`, `flask`, `django`, `laravel`, `rails`, `spring`, `aspnet-attributes`, `phoenix` |

## `kind: folder`: folder-based routing

```yaml
id: nextjs-app
kind: folder
about: "Next.js app router (app/**/page.tsx)"
roots: [app, src/app]            # folders to scan, relative to each project root
requires_any: ["next.config.js", "next.config.mjs", "next.config.ts", "package.json"]
page_files: ["page.tsx", "page.jsx", "page.ts", "page.js", "page.mdx"]
route_from: folder               # folder: route is the folder path; file: route is the file path
skip_segments: ["^\\(.*\\)$", "^@"]   # path parts dropped from the route (groups, slots)
skip_files: ["^_", "^api$"]      # path parts that make the whole file not a page
params:                          # how parameter segments are written → :name
  - "^\\[\\[?\\.\\.\\.(?P<name>\\w+)\\]?\\]$"
  - "^\\[(?P<name>\\w+)\\]$"
```

With `route_from: file`, `index_names: [index]` maps those file names to their folder.

`requires_any` lets one repository hold several apps. Every folder that holds one of these
files, at any depth, is a project root, and `roots` is looked for inside each. In a monorepo
with `admin/next.config.js` and `site/package.json`, both `admin/src/app` and `site/app` are
scanned. Without `requires_any` the pack applies at the repository root only.

## `kind: router`: route declarations found with ast-grep

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

The component name is resolved to a file through the code graph, so packs never describe
import syntax. When the captured text is not a plain name (Rails writes
`"registrations#new"`), two optional keys reshape it:

```yaml
component_match: "^[\"']?(?P<name>[\\w/]+)#"   # regex with a `name` group
component_format: "{pascal}Controller"           # {name} or {pascal}: registrations → RegistrationsController
```

A simpler pack, Express:

```yaml
id: express
kind: router
about: "Express-style app.get('/x', handler) and router.get('/x', handler)"
language: javascript
globs: ["**/*.js", "**/*.mjs", "**/*.cjs"]
rule:
  pattern: $APP.get($PATH, $$$HANDLERS)
captures:
  path: PATH
```

ast-grep never searches dependency or build folders (`node_modules`, `dist` and the like),
and a pack whose globs match no file in the repository is skipped.

## `kind: validator`

The pack format reserves a third kind for field constraints found with ast-grep:

```yaml
id: zod-string-min
kind: validator
about: z.string().min(n) inside an object schema
language: typescript
rule: { pattern: "$FIELD: z.string().min($MIN)" }
captures: { field: FIELD, min_length: MIN }
```

Validator packs would only add `EXTRACTED` facts that Claude Code otherwise reads itself,
making analysis cheaper but never required. **No validator packs ship today**, and the
loader reads folder and router packs.

## Writing a pack

See [Adding framework support](../contributing/framework-support.md) for the steps and the
tests each pack needs.
