import React from 'react';
import BarChart from './charts/BarChart';
import {getRelease, LATEST} from '@site/src/data';
import type {ResultRow} from '@site/src/data/types';
import {formatters} from './charts/format';

const LOWER_IS_BETTER: Array<keyof ResultRow> = [
  'hallucinationRate',
  'latencyP50',
  'costPer1k',
];

const FORMAT: Partial<Record<keyof ResultRow, keyof typeof formatters>> = {
  accuracy: 'percent',
  citationF1: 'percent',
  hallucinationRate: 'percent',
  latencyP50: 'seconds',
  costPer1k: 'usd',
  searchCalls: 'number',
};

/**
 * One metric from one release, ranked. Written for MDX:
 * `<MetricBar metric="accuracy" title="Accuracy" />`
 */
export default function MetricBar({
  metric,
  title,
  subtitle,
  release = LATEST,
  colorByProvider = false,
  footnote,
}: {
  metric: keyof ResultRow;
  title: string;
  subtitle?: string;
  release?: string;
  colorByProvider?: boolean;
  footnote?: string;
}) {
  const data = getRelease(release);
  const lower = LOWER_IS_BETTER.includes(metric);

  return (
    <BarChart
      title={title}
      subtitle={subtitle ?? `${release} · ${data.taskCount} tasks`}
      format={FORMAT[metric] ?? 'number'}
      lowerIsBetter={lower}
      footnote={footnote}
      data={data.rows.map((row) => ({
        label: row.model,
        value: row[metric] as number,
        group: colorByProvider ? row.provider : undefined,
      }))}
    />
  );
}
