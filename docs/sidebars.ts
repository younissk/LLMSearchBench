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
      items: [
        {
          type: 'category',
          label: 'Tool-use correctness',
          collapsed: false,
          link: {type: 'doc', id: 'tasks/tool-use-correctness/index'},
          items: [
            'tasks/tool-use-correctness/buckets',
            'tasks/tool-use-correctness/metrics',
            'tasks/tool-use-correctness/building',
            'tasks/tool-use-correctness/limitations',
            'tasks/tool-use-correctness/running',
            'tasks/tool-use-correctness/qwen-coverage',
            'tasks/tool-use-correctness/open-weight-coverage',
          ],
        },
        'tasks/search-quality',
      ],
    },
    {
      type: 'category',
      label: 'Results',
      collapsed: false,
      items: ['results/leaderboard', 'results/explore', 'examples-index'],
    },
    'data-format',
    'data-sources',
    'reproduce',
    'versioning',
  ],
};

export default sidebars;
