import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Methodology',
      collapsed: false,
      items: ['methodology/tasks', 'methodology/scoring', 'methodology/pipeline'],
    },
    {
      type: 'category',
      label: 'Tasks',
      collapsed: false,
      items: ['tasks/tool-use-correctness'],
    },
    {
      type: 'category',
      label: 'Results',
      collapsed: false,
      items: ['results/leaderboard', 'results/analysis'],
    },
    'data-format',
    'data-sources',
    'reproduce',
    'versioning',
  ],
};

export default sidebars;
