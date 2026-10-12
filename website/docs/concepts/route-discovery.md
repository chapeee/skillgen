---
title: Route discovery
description: How skillgendev finds an app's pages from folders, hint packs, Graphify, Claude Code and you, and merges them into routes.json.
---

# Route discovery

Frameworks matter for only one step: finding the list of routes. skillgendev tries these
sources and merges what they find into `.skillgendev/routes.json`.

| Source | Covered today |
| --- | --- |
| Folder routing (built in, from folder hint packs) | Next.js (app and pages router), Nuxt, SvelteKit, Astro |
| Routes declared in code (ast-grep router hint packs) | React Router, route objects (Vue Router, Angular, data routers), Express, Flask, Django, Laravel, Rails, Spring MVC, ASP.NET Core attributes, Phoenix |
| Graphify's own route nodes | ASP.NET Razor Pages (`@page "/x"`), Dart / Flutter navigation |
| Claude Code reading the code graph | Any other stack: Go, Rails `resources`, conventional MVC routes, custom routers, CMSs |
| You | `skillgendev routes --route /leads/import` |

Tested end to end on React Router, Next.js and Flask apps. The Rails, Spring, ASP.NET,
Phoenix and Laravel hint packs are tested on small sample apps, and the Claude step was
tried live on Rails and Go samples.

## How the Claude step works

Graphify does not name routes in most stacks, but its links show **hubs**: files such as a
router that link to many controllers, views or pages. skillgendev ranks those likely router files
and gives Claude Code the map ("this file links to these files"). Claude reads them read-only
and returns the routes with their entry files.

It runs automatically when no other source finds a route, or on demand:

```bash
skillgendev routes --all --ask-claude    # also let Claude list routes
skillgendev routes --all --no-claude     # never call Claude
```

The prompt is saved in `.skillgendev/route-listing-prompt.md` so you can see what was asked.

## Merging into routes.json

```bash
skillgendev routes --all
skillgendev routes --route /leads/import --route /audiences/:id   # add by hand, repeatable
skillgendev routes --all --include "campaigns/*" --exclude "api/*"
```

Each entry looks like this:

```json
{
  "route": "/campaigns/:campaignId/report",
  "skill": "acme-campaigns-report",
  "title": "",
  "entry_files": ["app/campaigns/[campaignId]/report/page.tsx"],
  "sources": ["folder:nextjs-app"],
  "has_form": null,
  "skip": false,
  "name_locked": false
}
```

You may edit `skill`, `title`, `skip` and `open`. Running `routes --all` again updates the file
from the current code:

- A route's code files are replaced by the ones found now.
- Routes the code no longer has are removed, **unless** you named, skipped or generated them.
- Names you chose are locked and never change; clashing generated names get `-2`, `-3`.
- `has_form` is filled in by `generate`: `false` routes are skipped later unless you pass
  `--force`.

Routes are normalised to one form, `/a/:id/b`, whatever the source wrote (`[id]`, `<id>`,
`{id}`). Dependency and build folders (`node_modules`, `dist`, hidden folders) are never
searched. Apps inside one repository, such as an admin app and a main site side by side,
are all found.

## Concrete pages

A route you give as one concrete page (`/audiences/7`) is linked to the pattern found in the
code (`/audiences/:id`). The pattern with the most fixed segments wins, and a tie links nothing.

## Teaching skillgendev a router

Add a small YAML file under `hintpacks/`; no Python needed. See
[Hint packs](../reference/hint-packs.md) and [Adding framework support](../contributing/framework-support.md).
