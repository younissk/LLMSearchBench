# LLMSearchBench documentation site

Docusaurus 3. See the [repository README](../README.md) for how this fits
together, and [the versioning policy](content/versioning.md) for how releases
are cut.

## Commands

| Command | What it does |
| --- | --- |
| `npm start` | dev server, hot reload |
| `npm run build` | production build into `build/` |
| `npm run serve` | serve the production build locally |
| `npm run typecheck` | `tsc`, also a CI gate |
| `npm run version:cut -- v0.1.0` | freeze `content/` as a versioned docs snapshot |

## Where things live

- **Prose** — `content/`, plain Markdown/MDX. KaTeX (`$…$`, `$$…$$`) and
  Mermaid fenced blocks both work out of the box.
- **Benchmark data** — `src/data/releases/*.json`, registered in
  `src/data/index.ts`. The shape is defined in `src/data/types.ts`.
- **Components** — `src/components/`. `ResultsGrid`, `BarChart`, `ScatterPlot`
  and `MetricBar` are globally available inside MDX without an import
  (registered in `src/theme/MDXComponents.tsx`).
- **Design tokens** — `src/css/custom.css`. Chart series colours are CSS custom
  properties (`--series-1` … `--series-5`) with separately chosen dark-mode
  steps.

## Changing chart colours

The series palette is validated for colour-vision deficiency and for contrast
against both surfaces. If you change a `--series-*` value, re-run the check
before committing:

```bash
node <dataviz-skill>/scripts/validate_palette.js \
  "#2a78d6,#eb6834,#1baf7a,#eda100,#e87ba4" --mode light
```

Scatter plots compare every pair of colours at once, so they are capped at the
first three slots; further groups fold into a neutral "Other".
