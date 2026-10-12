import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import { themes as prismThemes } from 'prism-react-renderer';
import tailwindcss from 'tailwindcss';

const organizationName = 'chapeee';
const projectName = 'skillgen';
const repositoryUrl = `https://github.com/${organizationName}/${projectName}`;
// The live site. DOCS_URL and DOCS_BASE_URL override it for previews or another host;
// canonical links, the sitemap and social cards all use this origin.
const SITE_URL = 'https://skillgen.dev';
const url = process.env.DOCS_URL?.replace(/\/+$/, '') || SITE_URL;
const baseUrl = process.env.DOCS_BASE_URL || '/';
const description =
  'skillgendev reads a web app’s code route by route and writes one Agent Skill per page, so Claude, Cowork or any AI with a browser can fill its forms in one call.';

const config: Config = {
  title: 'skillgendev',
  tagline: 'Compile an app’s code into one Agent Skill per page.',
  favicon: 'favicon.ico',
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

  headTags: [
    { tagName: 'link', attributes: { rel: 'icon', type: 'image/png', sizes: '32x32', href: `${baseUrl}img/favicon-32.png` } },
    { tagName: 'link', attributes: { rel: 'apple-touch-icon', sizes: '180x180', href: `${baseUrl}img/apple-touch-icon.png` } },
    { tagName: 'link', attributes: { rel: 'manifest', href: `${baseUrl}site.webmanifest` } },
    // Structured data so search engines can show skillgendev as a software result.
    {
      tagName: 'script',
      attributes: { type: 'application/ld+json' },
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@graph': [
          {
            '@type': 'SoftwareApplication',
            name: 'skillgendev',
            description,
            url: `${url}${baseUrl}`,
            applicationCategory: 'DeveloperApplication',
            operatingSystem: 'Windows, macOS, Linux',
            softwareRequirements: 'Python 3.10+',
            license: 'https://www.apache.org/licenses/LICENSE-2.0',
            downloadUrl: 'https://pypi.org/project/skillgendev/',
            installUrl: `${url}${baseUrl}docs/getting-started/installation/`,
            codeRepository: repositoryUrl,
            image: `${url}${baseUrl}img/social-card.png`,
            offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
          },
          {
            '@type': 'WebSite',
            name: 'skillgendev',
            url: `${url}${baseUrl}`,
          },
        ],
      }),
    },
  ],

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
        sitemap: {
          lastmod: 'date',
          changefreq: 'weekly',
          priority: 0.5,
          ignorePatterns: ['/search/**', '/tags/**'],
          filename: 'sitemap.xml',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Social platforms ignore SVG, so the card is a 1200×630 PNG.
    image: 'img/social-card.png',
    metadata: [
      { name: 'description', content: description },
      {
        name: 'keywords',
        content:
          'skillgendev, Agent Skills, Claude skills, AI form filling, browser agent, SKILL.md, Claude Code, Cowork, code to skill compiler, Playwright, web automation',
      },
      { name: 'author', content: 'skillgendev contributors' },
      { name: 'robots', content: 'index, follow, max-image-preview:large' },
      { name: 'twitter:card', content: 'summary_large_image' },
      { property: 'og:type', content: 'website' },
      { property: 'og:site_name', content: 'skillgendev' },
      { property: 'og:locale', content: 'en_US' },
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
