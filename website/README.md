# skillgendev documentation site

This directory contains the Docusaurus documentation site for
[`chapeee/skillgen`](https://github.com/chapeee/skillgen).

## Local development

Use Node.js 20 or later and npm. From this directory:

```bash
npm ci
npm start
```

Run `npm run build` to produce the static site in `build/` and
`npm run serve` to preview that output.

`npm run typecheck` checks the TypeScript configuration. Add pages under `docs/`;
the sidebar discovers them automatically. Use `sidebar_position` front matter
and `_category_.json` files to order pages and sections.

## Hosting URL

The site is built for `https://skillgen.dev/` (canonical links, sitemap and social
cards use that origin). Set `DOCS_URL` to a full origin and `DOCS_BASE_URL` to a path
when building for another host or a preview.

For GitHub Pages, choose **GitHub Actions** under the repository's **Settings →
Pages → Build and deployment → Source**. The docs workflow builds pull requests
and deploys pushes to `main`. Configure the optional URL variables as repository
Actions variables; configure a real custom domain and its DNS separately in
Pages settings if you choose to use one.
