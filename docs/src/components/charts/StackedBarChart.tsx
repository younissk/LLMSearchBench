import React, {useState} from 'react';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';
import {pct} from './format';

export interface StackedSeries {
  key: string;
  label: string;
  color: string;
}

export interface StackedRow {
  label: string;
  /** Raw counts, keyed by series. Normalised to 100% per row. */
  values: Record<string, number>;
}

export interface StackedBarChartProps {
  rows: StackedRow[];
  series: StackedSeries[];
  title: string;
  subtitle?: string;
  /** Series key to sort rows by, descending. */
  sortBy?: string;
  footnote?: string;
  labelWidth?: number;
}

const BAR_HEIGHT = 20;
const BAR_GAP = 8;
const SEGMENT_GAP = 2; // surface shows through between segments

/**
 * One row per model, the whole run in it.
 *
 * Normalised to 100% because the question is composition — what share of a
 * run went each way — not volume; every row has the same 360 items anyway.
 */
export default function StackedBarChart({
  rows,
  series,
  title,
  subtitle,
  sortBy,
  footnote,
  labelWidth = 150,
}: StackedBarChartProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<number | null>(null);

  const total = (row: StackedRow) =>
    series.reduce((sum, s) => sum + (row.values[s.key] ?? 0), 0);

  const ordered = sortBy
    ? [...rows].sort(
        (a, b) => (b.values[sortBy] ?? 0) / (total(b) || 1) - (a.values[sortBy] ?? 0) / (total(a) || 1),
      )
    : rows;

  const padding = {top: 8, right: 16, bottom: 26, left: labelWidth};
  const innerWidth = Math.max(80, width - padding.left - padding.right);
  const innerHeight = ordered.length * (BAR_HEIGHT + BAR_GAP) - BAR_GAP;
  const height = innerHeight + padding.top + padding.bottom;

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
          .map(
            (row) =>
              `${row.label}: ${series
                .map((s) => `${s.label} ${pct((row.values[s.key] ?? 0) / (total(row) || 1))}`)
                .join(', ')}`,
          )
          .join('; ')}`}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <text
            key={t}
            className={styles.axisLabel}
            x={padding.left + t * innerWidth}
            y={padding.top + innerHeight + 16}
            textAnchor={t === 0 ? 'start' : t === 1 ? 'end' : 'middle'}
          >
            {pct(t, 0)}
          </text>
        ))}

        {ordered.map((row, i) => {
          const y = padding.top + i * (BAR_HEIGHT + BAR_GAP);
          const sum = total(row) || 1;
          let cursor = padding.left;
          return (
            <g key={row.label} onMouseEnter={() => setHover(i)}>
              <rect
                className={styles.hit}
                x={0}
                y={y - BAR_GAP / 2}
                width={Math.max(width, 1)}
                height={BAR_HEIGHT + BAR_GAP}
              />
              <text
                className={styles.categoryLabel}
                x={padding.left - 10}
                y={y + BAR_HEIGHT / 2}
                textAnchor="end"
                dominantBaseline="central"
              >
                {row.label}
              </text>
              {series.map((s) => {
                const share = (row.values[s.key] ?? 0) / sum;
                const w = share * innerWidth;
                const x = cursor;
                cursor += w;
                if (w <= 0) return null;
                return (
                  <rect
                    key={s.key}
                    x={x}
                    y={y}
                    width={Math.max(w - SEGMENT_GAP, 0.5)}
                    height={BAR_HEIGHT}
                    rx={2}
                    fill={s.color}
                    opacity={hover === null || hover === i ? 1 : 0.4}
                  />
                );
              })}
            </g>
          );
        })}
      </svg>

      <div className={styles.legend}>
        {series.map((s) => (
          <span key={s.key} className={styles.legendItem}>
            <span className={styles.legendSwatch} style={{background: s.color}} />
            {s.label}
          </span>
        ))}
      </div>

      {hover !== null && (
        <Tooltip
          x={padding.left + 20}
          y={padding.top + hover * (BAR_HEIGHT + BAR_GAP) + (subtitle ? 74 : 54)}
          title={ordered[hover].label}
          rows={series.map((s) => ({
            label: s.label,
            value: `${ordered[hover].values[s.key] ?? 0} · ${pct(
              (ordered[hover].values[s.key] ?? 0) / (total(ordered[hover]) || 1),
            )}`,
            color: s.color,
          }))}
        />
      )}

      <div className={styles.footnote}>{footnote ?? 'Each row is one whole run.'}</div>
    </figure>
  );
}
