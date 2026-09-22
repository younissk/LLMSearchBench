import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import {execSync} from 'node:child_process';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

/** Last-update stamps read git log, which fails hard on a repo with no commits. */
const hasGitHistory = (() => {
  try {
    execSync('git rev-parse HEAD', {stdio: 'ignore'});
    return true;
  } catch {
    return false;
  }
})();

const ORG = 'younissk';
const REPO = 'LLMSearchBench';

const config: Config = {
  title: 'LLMSearchBench',
  tagline: 'A small, reproducible benchmark for LLM search behaviour',
  favicon: 'img/favicon.svg',

  url: `https://${ORG}.github.io`,
  baseUrl: `/${REPO}/`,
  organizationName: ORG,
  projectName: REPO,
  trailingSlash: false,

  onBrokenLinks: 'throw',
  onDuplicateRoutes: 'throw',

  future: {
    v4: true,
    faster: false, // flip to true for the Rspack build once deps settle
  },

  i18n: {defaultLocale: 'en', locales: ['en']},

  markdown: {
    mermaid: true,
    format: 'detect',
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },
  themes: [
    '@docusaurus/theme-mermaid',
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {
        hashed: true,
        docsDir: 'content',
        blogDir: 'changelog',
        indexDocs: true,
        indexBlog: true,
        indexPages: true,
        docsRouteBasePath: '/docs',
        blogRouteBasePath: '/changelog',
        highlightSearchTermsOnTargetPage: true,
        explicitSearchResultPath: true,
        searchBarShortcutHint: false,
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          path: 'content',
          routeBasePath: 'docs',
          sidebarPath: './sidebars.ts',
          editUrl: `https://github.com/${ORG}/${REPO}/tree/main/docs/`,
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex],
          // Benchmark + page versioning. `npm run version:cut -- v0.2.0`
          lastVersion: 'current',
          versions: {
            current: {
              label: 'v0.1.0 (latest)',
              path: '',
              banner: 'none',
            },
          },
          showLastUpdateTime: hasGitHistory,
        },
        blog: {
          path: 'changelog',
          routeBasePath: 'changelog',
          blogTitle: 'Changelog',
          blogDescription: 'Every change to the benchmark, its data, and this site.',
          blogSidebarTitle: 'Releases',
          blogSidebarCount: 'ALL',
          showReadingTime: false,
          onUntruncatedBlogPosts: 'ignore',
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex],
          feedOptions: {
            type: 'all',
            title: 'LLMSearchBench changelog',
            copyright: `Copyright © ${new Date().getFullYear()} ${ORG}`,
          },
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  stylesheets: [],

  themeConfig: {
    image: 'img/social-card.png',
    colorMode: {
      defaultMode: 'light',
      respectPrefersColorScheme: true,
    },
    docs: {
      sidebar: {hideable: true, autoCollapseCategories: false},
    },
    mermaid: {
      theme: {light: 'neutral', dark: 'dark'},
    },
    navbar: {
      title: 'LLMSearchBench',
      logo: {alt: '', src: 'img/logo.svg'},
      items: [
        {type: 'docSidebar', sidebarId: 'docsSidebar', position: 'left', label: 'Docs'},
        {to: '/results', label: 'Results', position: 'left'},
        {to: '/changelog', label: 'Changelog', position: 'left'},
        {type: 'docsVersionDropdown', position: 'right'},
        {href: `https://github.com/${ORG}/${REPO}`, label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'light',
      links: [
        {
          title: 'Benchmark',
          items: [
            {label: 'Overview', to: '/docs/intro'},
            {label: 'Methodology', to: '/docs/methodology/scoring'},
            {label: 'Results', to: '/results'},
          ],
        },
        {
          title: 'Reproduce',
          items: [
            {label: 'Run it yourself', to: '/docs/reproduce'},
            {label: 'Data format', to: '/docs/data-format'},
          ],
        },
        {
          title: 'More',
          items: [
            {label: 'Changelog', to: '/changelog'},
            {label: 'GitHub', href: `https://github.com/${ORG}/${REPO}`},
          ],
        },
      ],
      copyright: `LLMSearchBench · CC BY 4.0 · ${new Date().getFullYear()}`,
    },
    prism: {
      additionalLanguages: ['bash', 'json', 'python', 'toml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
