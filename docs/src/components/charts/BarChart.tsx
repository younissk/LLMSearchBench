import React, {useState} from 'react';
import clsx from 'clsx';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';
import {formatters, type Formatter} from './format';

export interface BarDatum {
  label: string;
  value: number;
  /** Optional identity used for colour; assigned to fixed slots in first-seen order. */
  group?: string;
}

const SERIES_SLOTS = [
  'var(--series-1)',
  'var(--series-2)',
  'var(--series-3)',
  'var(--series-4)',
  'var(--series-5)',
];

export interface BarChartProps {
  data: BarDatum[];
  title: string;
  subtitle?: string;
  /** Formatter name, or your own function. */
  format?: keyof typeof formatters | Formatter;
  /** Sort descending by value before drawing. Default true. */
  sort?: boolean;
  /** true when a smaller value is the better result (cost, latency, hallucination). */
  lowerIsBetter?: boolean;
  footnote?: string;
  /** Pixel width reserved for the category labels. */
  labelWidth?: number;
}

const BAR_HEIGHT = 22;
const BAR_GAP = 10; // >= 2px surface gap between adjacent bars
const RADIUS = 4; // rounded data-end

/** Bar with square baseline corners and a 4px rounded data-end. */
function barPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(RADIUS, Math.max(0, w));
  return [
    `M${x},${y}`,
    `H${x + w - r}`,
    `A${r},${r} 0 0 1 ${x + w},${y + r}`,
    `V${y + h - r}`,
    `A${r},${r} 0 0 1 ${x + w - r},${y + h}`,
    `H${x}`,
    'Z',
  ].join(' ');
}

export default function BarChart({
  data,
  title,
  subtitle,
  format = 'number',
  sort = true,
  lowerIsBetter = false,
  footnote,
  labelWidth = 132,
}: BarChartProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<number | null>(null);

  const fmt: Formatter =
    typeof format === 'function' ? format : (formatters[format] ?? formatters.number);

  // best-first: descending normally, ascending when a smaller number is better
  const rows = sort
    ? [...data].sort((a, b) => (lowerIsBetter ? a.value - b.value : b.value - a.value))
    : data;

  const groups = Array.from(
    new Set(rows.map((r) => r.group).filter((g): g is string => Boolean(g))),
  );
  const colorOf = (d: BarDatum) =>
    d.group ? SERIES_SLOTS[groups.indexOf(d.group) % SERIES_SLOTS.length] : SERIES_SLOTS[0];

  const padding = {top: 8, right: 78, bottom: 26, left: labelWidth};
  const innerWidth = Math.max(80, width - padding.left - padding.right);
  const innerHeight = rows.length * (BAR_HEIGHT + BAR_GAP) - BAR_GAP;
  const height = innerHeight + padding.top + padding.bottom;

  const max = Math.max(...rows.map((r) => r.value), 0);
  const scale = (v: number) => (max === 0 ? 0 : (v / max) * innerWidth);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);

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
        aria-label={`${title}. ${rows
          .map((r) => `${r.label} ${fmt(r.value)}`)
          .join(', ')}`}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t, i) => (
          <line
            key={i}
            className={styles.grid}
            x1={padding.left + scale(t)}
            x2={padding.left + scale(t)}
            y1={padding.top}
            y2={padding.top + innerHeight}
          />
        ))}
        <line
          className={styles.axis}
          x1={padding.left}
          x2={padding.left}
          y1={padding.top}
          y2={padding.top + innerHeight}
        />

        {rows.map((row, i) => {
          const y = padding.top + i * (BAR_HEIGHT + BAR_GAP);
          const w = scale(row.value);
          const active = hover === i;
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
              <path
                d={barPath(padding.left, y, Math.max(w, 1), BAR_HEIGHT)}
                fill={colorOf(row)}
                opacity={hover === null || active ? 1 : 0.45}
              />
              {/* direct label: also the relief for sub-3:1 fills on the light surface */}
              <text
                className={styles.valueLabel}
                x={padding.left + w + 8}
                y={y + BAR_HEIGHT / 2}
                dominantBaseline="central"
              >
                {fmt(row.value)}
              </text>
            </g>
          );
        })}

        {ticks.map((t, i) => (
          <text
            key={i}
            className={styles.axisLabel}
            x={padding.left + scale(t)}
            y={padding.top + innerHeight + 16}
            textAnchor={i === 0 ? 'start' : 'middle'}
          >
            {fmt(t)}
          </text>
        ))}
      </svg>

      {groups.length > 1 && (
        <div className={styles.legend}>
          {groups.map((g, i) => (
            <span key={g} className={styles.legendItem}>
              <span
                className={styles.legendSwatch}
                style={{background: SERIES_SLOTS[i % SERIES_SLOTS.length]}}
              />
              {g}
            </span>
          ))}
        </div>
      )}

      {hover !== null && (
        <Tooltip
          x={padding.left + scale(rows[hover].value) / 2}
          y={
            padding.top +
            hover * (BAR_HEIGHT + BAR_GAP) +
            BAR_HEIGHT / 2 +
            (subtitle ? 78 : 58)
          }
          title={rows[hover].label}
          rows={[
            ...(rows[hover].group
              ? [{label: 'Group', value: rows[hover].group as string}]
              : []),
            {label: 'Value', value: fmt(rows[hover].value), color: colorOf(rows[hover])},
          ]}
        />
      )}

      <div className={clsx(styles.footnote)}>
        {footnote ??
          (lowerIsBetter ? 'Lower is better.' : 'Higher is better.')}
      </div>
    </figure>
  );
}
