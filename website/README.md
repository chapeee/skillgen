# skillgendev documentation site

This directory contains the Docusaurus documentation site for
[`chapeee/skillprinter`](https://github.com/chapeee/skillprinter).

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

The config targets the repository's GitHub Pages project URL by default:
`https://chapeee.github.io/skillprinter/`. Set `DOCS_URL` to a full origin or
`DOCS_DOMAIN` to a hostname when deploying to another host. `DOCS_BASE_URL`
can override the path (for example, `/skillprinter/` for a GitHub Pages project
site). A custom origin defaults to `/`. No custom domain is required or assumed.

For GitHub Pages, choose **GitHub Actions** under the repository's **Settings →
Pages → Build and deployment → Source**. The docs workflow builds pull requests
and deploys pushes to `main`. Configure the optional URL variables as repository
Actions variables; configure a real custom domain and its DNS separately in
Pages settings if you choose to use one.
