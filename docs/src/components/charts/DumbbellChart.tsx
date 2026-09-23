import React, {useState} from 'react';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';
import {formatters, type Formatter} from './format';

export interface DumbbellRow {
  label: string;
  from: number;
  to: number;
}

export interface DumbbellChartProps {
  rows: DumbbellRow[];
  title: string;
  subtitle?: string;
  fromLabel: string;
  toLabel: string;
  format?: keyof typeof formatters | Formatter;
  /** Sort by the size of the gap rather than by either end. Default true. */
  sortByGap?: boolean;
  footnote?: string;
  labelWidth?: number;
}

const ROW_HEIGHT = 22;
const ROW_GAP = 8;
const DOT_R = 5;

/**
 * Two measurements of the same model, joined.
 *
 * The line is the point: the distance between normal and adversarial accuracy
 * is the thing being read, and two separate bar charts hide it.
 */
export default function DumbbellChart({
  rows,
  title,
  subtitle,
  fromLabel,
  toLabel,
  format = 'percent',
  sortByGap = true,
  footnote,
  labelWidth = 150,
}: DumbbellChartProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<number | null>(null);

  const fmt: Formatter =
    typeof format === 'function' ? format : (formatters[format] ?? formatters.number);

  const ordered = sortByGap
    ? [...rows].sort((a, b) => a.to - a.from - (b.to - b.from))
    : rows;

  const padding = {top: 10, right: 62, bottom: 26, left: labelWidth};
  const innerWidth = Math.max(80, width - padding.left - padding.right);
  const innerHeight = ordered.length * (ROW_HEIGHT + ROW_GAP) - ROW_GAP;
  const height = innerHeight + padding.top + padding.bottom;

  const lo = Math.min(...ordered.flatMap((r) => [r.from, r.to]), 0);
  const hi = Math.max(...ordered.flatMap((r) => [r.from, r.to]), 0.01);
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
          .map((r) => `${r.label}: ${fmt(r.from)} to ${fmt(r.to)}`)
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

        {ordered.map((row, i) => {
          const y = padding.top + i * (ROW_HEIGHT + ROW_GAP) + ROW_HEIGHT / 2;
          const dim = hover !== null && hover !== i;
          return (
            <g key={row.label} onMouseEnter={() => setHover(i)} opacity={dim ? 0.4 : 1}>
              <rect
                className={styles.hit}
                x={0}
                y={y - (ROW_HEIGHT + ROW_GAP) / 2}
                width={Math.max(width, 1)}
                height={ROW_HEIGHT + ROW_GAP}
              />
              <text
                className={styles.categoryLabel}
                x={padding.left - 10}
                y={y}
                textAnchor="end"
                dominantBaseline="central"
              >
                {row.label}
              </text>
              <line
                x1={sx(row.from)}
                x2={sx(row.to)}
                y1={y}
                y2={y}
                stroke="var(--lsb-axis)"
                strokeWidth={2}
              />
              <circle
                cx={sx(row.from)}
                cy={y}
                r={DOT_R}
                fill="var(--series-1)"
                stroke="var(--lsb-surface)"
                strokeWidth={2}
              />
              <circle
                cx={sx(row.to)}
                cy={y}
                r={DOT_R}
                fill="var(--series-2)"
                stroke="var(--lsb-surface)"
                strokeWidth={2}
              />
              <text
                className={styles.valueLabel}
                x={padding.left + innerWidth + 8}
                y={y}
                dominantBaseline="central"
              >
                {fmt(row.to - row.from)}
              </text>
            </g>
          );
        })}
      </svg>

      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.legendSwatch} style={{background: 'var(--series-1)'}} />
          {fromLabel}
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendSwatch} style={{background: 'var(--series-2)'}} />
          {toLabel}
        </span>
      </div>

      {hover !== null && (
        <Tooltip
          x={Math.min(sx(ordered[hover].to) + 12, width - 160)}
          y={padding.top + hover * (ROW_HEIGHT + ROW_GAP) + (subtitle ? 74 : 54)}
          title={ordered[hover].label}
          rows={[
            {label: fromLabel, value: fmt(ordered[hover].from), color: 'var(--series-1)'},
            {label: toLabel, value: fmt(ordered[hover].to), color: 'var(--series-2)'},
            {label: 'Change', value: fmt(ordered[hover].to - ordered[hover].from)},
          ]}
        />
      )}

      <div className={styles.footnote}>
        {footnote ?? 'The number on the right is the change between the two dots.'}
      </div>
    </figure>
  );
}
