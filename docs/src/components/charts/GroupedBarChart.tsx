import React, {useState} from 'react';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';
import {pct} from './format';

export interface GroupedSeries {
  key: string;
  label: string;
  color: string;
  /** The value a perfect model would show. Drawn as a target tick. */
  target?: number;
}

export interface GroupedRow {
  label: string;
  values: Record<string, number>;
}

export interface GroupedBarChartProps {
  rows: GroupedRow[];
  series: GroupedSeries[];
  title: string;
  subtitle?: string;
  sortBy?: string;
  footnote?: string;
  labelWidth?: number;
}

const BAR_HEIGHT = 9;
const BAR_GAP = 2; // surface gap between bars of one group
const GROUP_GAP = 12;

/**
 * Several measures per model, side by side rather than stacked.
 *
 * Used where the measures are not parts of a whole — three bucket search
 * rates do not add up to anything, so stacking them would invent a total.
 */
export default function GroupedBarChart({
  rows,
  series,
  title,
  subtitle,
  sortBy,
  footnote,
  labelWidth = 150,
}: GroupedBarChartProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<number | null>(null);

  const ordered = sortBy
    ? [...rows].sort((a, b) => (b.values[sortBy] ?? 0) - (a.values[sortBy] ?? 0))
    : rows;

  const groupHeight = series.length * BAR_HEIGHT + (series.length - 1) * BAR_GAP;
  const padding = {top: 8, right: 16, bottom: 26, left: labelWidth};
  const innerWidth = Math.max(80, width - padding.left - padding.right);
  const innerHeight = ordered.length * (groupHeight + GROUP_GAP) - GROUP_GAP;
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
                .map((s) => `${s.label} ${pct(row.values[s.key] ?? 0)}`)
                .join(', ')}`,
          )
          .join('; ')}`}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line
              className={styles.grid}
              x1={padding.left + t * innerWidth}
              x2={padding.left + t * innerWidth}
              y1={padding.top}
              y2={padding.top + innerHeight}
            />
            <text
              className={styles.axisLabel}
              x={padding.left + t * innerWidth}
              y={padding.top + innerHeight + 16}
              textAnchor={t === 0 ? 'start' : t === 1 ? 'end' : 'middle'}
            >
              {pct(t, 0)}
            </text>
          </g>
        ))}

        {ordered.map((row, i) => {
          const top = padding.top + i * (groupHeight + GROUP_GAP);
          return (
            <g key={row.label} onMouseEnter={() => setHover(i)}>
              <rect
                className={styles.hit}
                x={0}
                y={top - GROUP_GAP / 2}
                width={Math.max(width, 1)}
                height={groupHeight + GROUP_GAP}
              />
              <text
                className={styles.categoryLabel}
                x={padding.left - 10}
                y={top + groupHeight / 2}
                textAnchor="end"
                dominantBaseline="central"
              >
                {row.label}
              </text>
              {series.map((s, j) => {
                const y = top + j * (BAR_HEIGHT + BAR_GAP);
                const w = Math.max((row.values[s.key] ?? 0) * innerWidth, 1);
                return (
                  <g key={s.key}>
                    <rect
                      x={padding.left}
                      y={y}
                      width={w}
                      height={BAR_HEIGHT}
                      rx={2}
                      fill={s.color}
                      opacity={hover === null || hover === i ? 1 : 0.4}
                    />
                    {s.target != null && (
                      <line
                        x1={padding.left + s.target * innerWidth}
                        x2={padding.left + s.target * innerWidth}
                        y1={y - 1}
                        y2={y + BAR_HEIGHT + 1}
                        stroke="var(--lsb-ink)"
                        strokeWidth={1.5}
                      />
                    )}
                  </g>
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
            {s.target != null && ` (target ${pct(s.target, 0)})`}
          </span>
        ))}
      </div>

      {hover !== null && (
        <Tooltip
          x={padding.left + 20}
          y={padding.top + hover * (groupHeight + GROUP_GAP) + (subtitle ? 74 : 54)}
          title={ordered[hover].label}
          rows={series.map((s) => ({
            label: s.label,
            value: pct(ordered[hover].values[s.key] ?? 0),
            color: s.color,
          }))}
        />
      )}

      <div className={styles.footnote}>
        {footnote ?? 'The dark tick on each bar is the value a perfect model would show.'}
      </div>
    </figure>
  );
}
