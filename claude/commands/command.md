---
description: Generate Agent Skills that fill this app's forms, one per route. Usage: /{{tool}} /some/route, /{{tool}} all, or /{{tool}} all --name acme
argument-hint: "/route | all [--name prefix]"
---

Generate page skills with {{tool}} for: $ARGUMENTS

Follow the `{{tool}}` skill. In short:

1. If `.{{tool}}/config.json` does not exist, run `{{tool}} init` (ask the user for the app's
   display name and, if they have one, a dev URL).
2. For `all`: run `{{tool}} routes --all --json`, show the routes, and let the user drop or
   rename any before generating. For one route, use it as given.
3. Run `{{tool}} generate --route <route> --json` (or `--all`), passing `--name` through
   and `--xy` when the user wants x/y.
4. Follow each result's `next`, as the `{{tool}}` skill says, until nothing is left:
   `analyse` means you read the prompt and write the analysis yourself (one
   `{{tool}}-route-analyzer` subagent per route for several); `ask` means you ask the user
   its question in chat, run `run` on a yes, then run `then`. A result with status
   `exists` asks before a skill is recreated.
5. Report each skill folder and any open questions. Ask the user the open questions from
   `{{tool}} questions --json`, record answers with `{{tool}} answer <id> "<answer>"`, then
   generate again with `--overwrite`: the user is updating a skill they just made.
