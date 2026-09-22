import MDXComponents from '@theme-original/MDXComponents';
import ResultsGrid from '@site/src/components/ResultsGrid';
import BarChart from '@site/src/components/charts/BarChart';
import ScatterPlot from '@site/src/components/charts/ScatterPlot';
import MetricBar from '@site/src/components/MetricBar';

/** Available in every .md/.mdx file without an import. */
export default {
  ...MDXComponents,
  ResultsGrid,
  BarChart,
  ScatterPlot,
  MetricBar,
};
