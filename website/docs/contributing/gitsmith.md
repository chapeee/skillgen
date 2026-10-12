---
title: Commits with Gitsmith
description: Use Gitsmith, a Conventional Commits CLI from skillgendev's maintainer, to write commits that follow skillgendev's rules.
---

# Commits with Gitsmith

skillgendev asks every contributor for [Conventional Commits](https://www.conventionalcommits.org/):
`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, one small change per commit.
[Gitsmith](https://www.npmjs.com/package/gitsmith) is an open-source commit CLI from the same
maintainer that makes this easy. It is optional: skillgendev does not depend on it, and any way of
writing a correct message is fine.

## What Gitsmith does

Facts below are from Gitsmith's published README (version 0.2.1, MIT licence, Node.js 20 or
newer).

- It prompts you through your project's commit format, defined in one `.commitconfig.json`
  that it finds by walking up from the current folder.
- It validates the config and reports clear errors.
- It checks that you are in a git repository and have staged files.
- It shows a preview of the message and asks for confirmation before it runs `git commit`.
- Optionally, it suggests a message from a plain description of what you did, using a free
  NVIDIA AI API key. Only the text you type is sent; source code and diffs are not. Without a
  key, or with AI disabled, it falls back to the manual prompts.

## Set it up for skillgendev

```bash
npm install -g gitsmith
cd skillprinter
gitsmith init        # creates .commitconfig.json with a Conventional Commits default
```

Then edit `.commitconfig.json` so its types match the ones skillgendev uses. A config that fits
this repository, with scopes named after its packages:

```json
{
  "types": ["feat", "fix", "docs", "test", "refactor", "chore"],
  "askScope": true,
  "scopes": ["routes", "graph", "analyze", "compile", "generate", "probe", "export", "cli", "docs", "website"],
  "askTicket": false,
  "askBreaking": true,
  "format": "{type}({scope}): {message}",
  "headerMaxLength": 72
}
```

The format tokens are `{type}`, `{scope}`, `{ticket}`, `{message}` and `{breaking}` (`!` when
the change is breaking). Scoped messages such as `feat(analyze): …` and `refactor(probe): …`
already appear in the repository's history.

:::note
`gitsmith init` writes the config into the current folder. Whether to commit a
`.commitconfig.json` to the repository is the maintainers' call; until then, keep yours local
(for example, list it in `.git/info/exclude`).
:::

## Commit

```bash
git add src/skillgen/routes/paths.py tests/test_paths.py
gitsmith
```

Gitsmith asks for the type, scope, message and whether the change is breaking, shows the final
header, and commits on confirmation:

```text
fix(routes): refuse Windows paths that Git Bash makes of /routes
```

### With AI suggestions

```bash
gitsmith key:set     # save an NVIDIA API key (free at build.nvidia.com)
gitsmith --ai        # describe what you did; pick or edit the suggestion
gitsmith --no-ai     # skip the AI prompt for this run
```

`key:show`, `key:status` and `key:remove` manage the saved key. In CI or scripts, set
`GITSMITH_AI_KEY` instead; it overrides the saved key.

## Why it fits skillgendev

- **Clean history makes `skillgendev check --since` easier to use.** Small, well-labelled commits
  make it clear which change made a skill stale, and which commit to compare against.
- **Same rule, less friction.** The contribution rules ask for Conventional Commits and small
  commits; Gitsmith turns that into a prompt instead of a checklist.
- **Docs pull requests too.** Changes to this site are commits like any other: use the
  `docs` type and the `website` scope.
