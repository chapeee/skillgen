import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

// The sidebar is written out rather than generated, so the reading order is a
// decision: start, then the guides you need daily, then how it works inside.
const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Getting started',
      collapsed: false,
      items: [
        'getting-started/installation',
        'getting-started/quick-start',
        'getting-started/using-skills',
      ],
    },
    {
      type: 'category',
      label: 'Guides',
      collapsed: false,
      items: [
        'guides/claude-code',
        'guides/generating-skills',
        'guides/xy-layout',
        'guides/hidden-forms',
        'guides/questions-and-rules',
        'guides/exporting',
        'guides/keeping-current',
        'guides/logs-and-debugging',
      ],
    },
    {
      type: 'category',
      label: 'Concepts',
      items: [
        'concepts/how-it-works',
        'concepts/route-discovery',
        'concepts/page-model',
        'concepts/skill-anatomy',
        'concepts/agent-handoff',
        'concepts/security',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      items: [
        'reference/cli',
        'reference/json-output',
        'reference/configuration',
        'reference/workspace',
        'reference/hint-packs',
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/overview',
        'architecture/pipeline',
        'architecture/fill-scripts',
        'architecture/modules',
        'architecture/decisions',
      ],
    },
    {
      type: 'category',
      label: 'Contributing',
      link: { type: 'doc', id: 'contributing/index' },
      items: [
        'contributing/development-setup',
        'contributing/coding-standards',
        'contributing/testing',
        'contributing/adding-commands',
        'contributing/framework-support',
        'contributing/documentation',
        'contributing/gitsmith',
      ],
    },
    'troubleshooting',
    'faq',
  ],
};

export default sidebars;
