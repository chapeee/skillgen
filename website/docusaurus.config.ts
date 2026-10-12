import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import { themes as prismThemes } from 'prism-react-renderer';
import tailwindcss from 'tailwindcss';

const organizationName = 'chapeee';
const projectName = 'skillprinter';
const repositoryUrl = `https://github.com/${organizationName}/${projectName}`;
const pagesUrl = `https://${organizationName}.github.io`;

// GitHub Pages uses the repository project URL by default. Set DOCS_URL to a
// full origin or DOCS_DOMAIN to a hostname when the site is hosted elsewhere;
// no custom domain is assumed by this configuration.
const configuredDomain = process.env.DOCS_DOMAIN?.replace(/^https?:\/\//, '').replace(/\/+$/, '');
// Vercel, Netlify, Cloudflare Pages and Cloudflare Workers serve a site at the
// root of their own domain, so their build variables mean "not GitHub Pages".
const isRootHost = Boolean(process.env.WORKERS_CI || process.env.CF_PAGES);
const vercelDomain = process.env.VERCEL_PROJECT_PRODUCTION_URL || process.env.VERCEL_URL;
const hostUrl =
  (vercelDomain ? `https://${vercelDomain}` : '') ||
  (process.env.NETLIFY ? process.env.URL : '') ||
  process.env.CF_PAGES_URL ||
  '';
const url =
  process.env.DOCS_URL?.replace(/\/+$/, '') ||
  (configuredDomain ? `https://${configuredDomain}` : '') ||
  hostUrl.replace(/\/+$/, '') ||
  pagesUrl;
// A custom origin serves at its root unless a subpath is explicitly configured.
const baseUrl = process.env.DOCS_BASE_URL || (url === pagesUrl && !isRootHost ? `/${projectName}/` : '/');

const config: Config = {
  title: 'skillgendev',
  tagline: 'Compile an app’s code into one Agent Skill per page.',
  favicon: 'img/favicon.png',
  url,
  baseUrl,
  organizationName,
  projectName,
  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  trailingSlash: true,

  markdown: {
    // `.md` is plain CommonMark, so contributors can write `<skill>` or
    // `{type}` in prose safely; only `.mdx` pages use React components.
    format: 'detect',
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  clientModules: ['./src/client/fonts.ts'],

  plugins: [
    // Tailwind runs as a PostCSS plugin inside Docusaurus's own CSS pipeline,
    // ahead of the autoprefixer Docusaurus already configures.
    function tailwindPlugin() {
      return {
        name: 'skillgendev-tailwind',
        configurePostCss(postcssOptions: { plugins: unknown[] }) {
          postcssOptions.plugins = [tailwindcss, ...postcssOptions.plugins];
          return postcssOptions;
        },
      };
    },
  ],

  themes: [
    '@docusaurus/theme-mermaid',
    [
      '@easyops-cn/docusaurus-search-local',
      {
        hashed: true,
        indexBlog: false,
        indexPages: false,
        docsRouteBasePath: '/docs',
        highlightSearchTermsOnTargetPage: true,
        explicitSearchResultPath: true,
        searchBarShortcutHint: true,
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: 'docs',
          sidebarPath: './sidebars.ts',
          showLastUpdateTime: true,
          // Every page links to its Markdown source; GitHub opens a fork and a
          // pull request for anyone without write access.
          editUrl: `${repositoryUrl}/edit/main/website/`,
        },
        blog: false,
        debug: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/skillgen-social-card.svg',
    metadata: [
      {
        name: 'description',
        content:
          'skillgendev reads a web app’s code route by route and writes one Agent Skill per page, so Claude, Cowork or any AI with a browser can fill its forms in one call.',
      },
      { name: 'theme-color', content: '#05070d' },
    ],
    colorMode: {
      defaultMode: 'dark',
      disableSwitch: false,
      respectPrefersColorScheme: false,
    },
    announcementBar: {
      id: 'pre-alpha',
      content:
        `skillgendev is pre-alpha and now on PyPI: <code>uv tool install skillgendev</code>. <a href="${baseUrl}docs/getting-started/installation/">Installation</a>.`,
      isCloseable: true,
    },
    docs: {
      sidebar: {
        hideable: true,
        autoCollapseCategories: false,
      },
    },
    navbar: {
      title: 'skillgendev',
      hideOnScroll: false,
      logo: {
        alt: 'skillgendev',
        src: 'img/skillgen-logo.png',
      },
      items: [
        { type: 'doc', docId: 'intro', position: 'left', label: 'Docs' },
        { type: 'doc', docId: 'guides/generating-skills', position: 'left', label: 'Guides' },
        { type: 'doc', docId: 'reference/cli', position: 'left', label: 'Reference' },
        { type: 'doc', docId: 'architecture/overview', position: 'left', label: 'Architecture' },
        { type: 'doc', docId: 'contributing/index', position: 'left', label: 'Contributing' },
        { type: 'search', position: 'right' },
        {
          href: repositoryUrl,
          position: 'right',
          className: 'header-github-link',
          'aria-label': 'GitHub repository',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Start',
          items: [
            { label: 'Overview', to: '/docs/' },
            { label: 'Installation', to: '/docs/getting-started/installation/' },
            { label: 'Quick start', to: '/docs/getting-started/quick-start/' },
            { label: 'Command reference', to: '/docs/reference/cli/' },
          ],
        },
        {
          title: 'Learn',
          items: [
            { label: 'How it works', to: '/docs/concepts/how-it-works/' },
            { label: 'Anatomy of a skill', to: '/docs/concepts/skill-anatomy/' },
            { label: 'Architecture', to: '/docs/architecture/overview/' },
            { label: 'Troubleshooting', to: '/docs/troubleshooting/' },
          ],
        },
        {
          title: 'Project',
          items: [
            { label: 'GitHub', href: repositoryUrl },
            { label: 'Issues', href: `${repositoryUrl}/issues` },
            { label: 'Contributing', to: '/docs/contributing/' },
            { label: 'Gitsmith', href: 'https://www.npmjs.com/package/gitsmith' },
          ],
        },
      ],
      copyright: `© ${new Date().getFullYear()} skillgendev contributors · Apache License 2.0`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.nightOwl,
      additionalLanguages: ['bash', 'powershell', 'diff', 'json', 'python', 'yaml', 'toml'],
    },
    mermaid: {
      theme: { light: 'neutral', dark: 'dark' },
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
