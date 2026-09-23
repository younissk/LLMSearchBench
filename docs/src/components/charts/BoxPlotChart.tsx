import React, {useState} from 'react';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';
import {formatters, type Formatter} from './format';

export interface BoxGroup {
  label: string;
  values: number[];
  /** Point labels, in the same order as `values`. */
  names?: string[];
}

export interface BoxPlotChartProps {
  groups: BoxGroup[];
  title: string;
  subtitle?: string;
  format?: keyof typeof formatters | Formatter;
  valueLabel: string;
  footnote?: string;
  labelWidth?: number;
}

const ROW_HEIGHT = 30;
const ROW_GAP = 6;

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 1) return sorted[0];
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  const next = sorted[base + 1] ?? sorted[base];
  return sorted[base] + (next - sorted[base]) * rest;
}

/**
 * Spread within a group, with every underlying model still drawn.
 *
 * A vendor average would let one strong model carry a weak family; the dots
 * keep the sample size visible, which matters at two or three models a vendor.
 */
export default function BoxPlotChart({
  groups,
  title,
  subtitle,
  format = 'percent',
  valueLabel,
  footnote,
  labelWidth = 150,
}: BoxPlotChartProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<{group: number; point: number} | null>(null);

  const fmt: Formatter =
    typeof format === 'function' ? format : (formatters[format] ?? formatters.number);

  const stats = groups.map((group) => {
    const order = group.values
      .map((value, i) => ({value, name: group.names?.[i] ?? ''}))
      .sort((a, b) => a.value - b.value);
    const sorted = order.map((o) => o.value);
    return {
      label: group.label,
      order,
      sorted,
      min: sorted[0] ?? 0,
      q1: quantile(sorted, 0.25),
      median: quantile(sorted, 0.5),
      q3: quantile(sorted, 0.75),
      max: sorted[sorted.length - 1] ?? 0,
    };
  });
  const ordered = [...stats].sort((a, b) => b.median - a.median);

  const padding = {top: 8, right: 16, bottom: 26, left: labelWidth};
  const innerWidth = Math.max(80, width - padding.left - padding.right);
  const innerHeight = ordered.length * (ROW_HEIGHT + ROW_GAP) - ROW_GAP;
  const height = innerHeight + padding.top + padding.bottom;

  const all = ordered.flatMap((g) => g.sorted);
  const lo = Math.min(...all, 0);
  const hi = Math.max(...all, 0.01);
  const sx = (v: number) => padding.left + ((v - lo) / (hi - lo || 1)) * innerWidth;

  return (
    <figure className={styles.figure} ref={ref}>
      <figcaption className={styles.caption}>
        <div className={styles.title}>{title}</div>
        {subtitle && <div className={styles.subtitle}>{subtitle}</div>}
      </figcaption>

      <svg
        className={styles.plot}
        width={width}
        height={height}
        role="img"
        aria-label={`${title}. ${ordered
          .map((g) => `${g.label}: median ${fmt(g.median)} over ${g.sorted.length} models`)
          .join('; ')}`}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const v = lo + t * (hi - lo);
          return (
            <g key={t}>
              <line
                className={styles.grid}
                x1={sx(v)}
                x2={sx(v)}
                y1={padding.top}
                y2={padding.top + innerHeight}
              />
              <text
                className={styles.axisLabel}
                x={sx(v)}
                y={padding.top + innerHeight + 16}
                textAnchor="middle"
              >
                {fmt(v)}
              </text>
            </g>
          );
        })}

        {ordered.map((group, i) => {
          const mid = padding.top + i * (ROW_HEIGHT + ROW_GAP) + ROW_HEIGHT / 2;
          return (
            <g key={group.label}>
              <text
                className={styles.categoryLabel}
                x={padding.left - 10}
                y={mid}
                textAnchor="end"
                dominantBaseline="central"
              >
                {group.label}
              </text>
              <line
                x1={sx(group.min)}
                x2={sx(group.max)}
                y1={mid}
                y2={mid}
                stroke="var(--lsb-axis)"
                strokeWidth={2}
              />
              <rect
                x={sx(group.q1)}
                y={mid - 9}
                width={Math.max(sx(group.q3) - sx(group.q1), 1)}
                height={18}
                rx={3}
                fill="var(--series-1)"
                opacity={0.22}
              />
              <line
                x1={sx(group.median)}
                x2={sx(group.median)}
                y1={mid - 10}
                y2={mid + 10}
                stroke="var(--series-1)"
                strokeWidth={2.5}
              />
              {group.sorted.map((value, j) => (
                <circle
                  key={j}
                  cx={sx(value)}
                  cy={mid}
                  r={4}
                  fill="var(--series-2)"
                  stroke="var(--lsb-surface)"
                  strokeWidth={1.5}
                  onMouseEnter={() => setHover({group: i, point: j})}
                />
              ))}
            </g>
          );
        })}
      </svg>

      {hover && (
        <Tooltip
          x={Math.min(sx(ordered[hover.group].sorted[hover.point]) + 12, width - 180)}
          y={padding.top + hover.group * (ROW_HEIGHT + ROW_GAP) + (subtitle ? 70 : 50)}
          title={ordered[hover.group].order[hover.point].name || ordered[hover.group].label}
          rows={[
            {
              label: valueLabel,
              value: fmt(ordered[hover.group].sorted[hover.point]),
              color: 'var(--series-2)',
            },
            {label: 'Vendor median', value: fmt(ordered[hover.group].median)},
            {label: 'Models', value: String(ordered[hover.group].sorted.length)},
          ]}
        />
      )}

      <div className={styles.footnote}>
        {footnote ??
          'The box is the middle half of the vendor and the line inside it the median; every dot is one model.'}
      </div>
    </figure>
  );
}
