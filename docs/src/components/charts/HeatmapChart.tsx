import React, {useState} from 'react';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';
import {formatters, type Formatter} from './format';

export interface HeatmapCell {
  row: string;
  column: string;
  /** null where there is nothing to show; drawn as an empty cell. */
  value: number | null;
  detail?: string;
}

export interface HeatmapChartProps {
  cells: HeatmapCell[];
  rows: string[];
  columns: string[];
  title: string;
  subtitle?: string;
  format?: keyof typeof formatters | Formatter;
  /** Ends of the colour scale. Defaults to the data's own range. */
  domain?: [number, number];
  rowLabel?: string;
  columnLabel?: string;
  footnote?: string;
  labelWidth?: number;
  cellHeight?: number;
}

/**
 * One hue, light to dark — the value is a magnitude, so a single ramp is the
 * honest encoding. A rainbow would imply categories that are not there.
 */
const RAMP = ['var(--seq-1)', 'var(--seq-2)', 'var(--seq-3)', 'var(--seq-4)', 'var(--seq-5)'];

const keyOf = (row: string, column: string) => `${row}::${column}`;

export default function HeatmapChart({
  cells,
  rows,
  columns,
  title,
  subtitle,
  format = 'percent',
  domain,
  rowLabel,
  columnLabel,
  footnote,
  labelWidth = 150,
  cellHeight = 20,
}: HeatmapChartProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<HeatmapCell | null>(null);

  const fmt: Formatter =
    typeof format === 'function' ? format : (formatters[format] ?? formatters.number);

  const values = cells.map((c) => c.value).filter((v): v is number => v != null);
  const [lo, hi] = domain ?? [Math.min(...values, 0), Math.max(...values, 1)];

  const byKey = new Map(cells.map((c) => [keyOf(c.row, c.column), c]));
  const step = (hi - lo) / RAMP.length || 1;
  const fill = (value: number) =>
    RAMP[Math.min(RAMP.length - 1, Math.max(0, Math.floor((value - lo) / step)))];

  const padding = {top: 66, right: 12, bottom: 12, left: labelWidth};
  const innerWidth = Math.max(80, width - padding.left - padding.right);
  const cellWidth = innerWidth / Math.max(columns.length, 1);
  const height = rows.length * cellHeight + padding.top + padding.bottom;

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
        aria-label={`${title}. ${rows.length} rows by ${columns.length} columns.`}
        onMouseLeave={() => setHover(null)}
      >
        {columns.map((column, j) => (
          <text
            key={column}
            className={styles.axisLabel}
            transform={`translate(${padding.left + j * cellWidth + cellWidth / 2} ${
              padding.top - 8
            }) rotate(-42)`}
          >
            {column}
          </text>
        ))}

        {rows.map((row, i) => (
          <g key={row}>
            <text
              className={styles.categoryLabel}
              x={padding.left - 10}
              y={padding.top + i * cellHeight + cellHeight / 2}
              textAnchor="end"
              dominantBaseline="central"
            >
              {row}
            </text>
            {columns.map((column, j) => {
              const cell = byKey.get(keyOf(row, column));
              const x = padding.left + j * cellWidth;
              const y = padding.top + i * cellHeight;
              const active = hover?.row === row && hover?.column === column;
              return (
                <rect
                  key={column}
                  x={x + 1}
                  y={y + 1}
                  width={Math.max(cellWidth - 2, 1)}
                  height={Math.max(cellHeight - 2, 1)}
                  rx={2}
                  fill={cell?.value == null ? 'var(--lsb-plane)' : fill(cell.value)}
                  stroke={active ? 'var(--lsb-ink)' : 'transparent'}
                  strokeWidth={1.5}
                  onMouseEnter={() => setHover(cell ?? {row, column, value: null})}
                />
              );
            })}
          </g>
        ))}
      </svg>

      <div className={styles.legend}>
        <span className={styles.legendItem}>{fmt(lo)}</span>
        {RAMP.map((color) => (
          <span key={color} className={styles.legendSwatch} style={{background: color}} />
        ))}
        <span className={styles.legendItem}>{fmt(hi)}</span>
      </div>

      {hover && (
        <Tooltip
          x={Math.min(
            padding.left + columns.indexOf(hover.column) * cellWidth + cellWidth,
            width - 190,
          )}
          y={padding.top + rows.indexOf(hover.row) * cellHeight + (subtitle ? 66 : 46)}
          title={hover.row}
          rows={[
            {label: columnLabel ?? 'Column', value: hover.column},
            {
              label: rowLabel ?? 'Value',
              value: hover.value == null ? 'no data' : fmt(hover.value),
            },
            ...(hover.detail ? [{label: 'Items', value: hover.detail}] : []),
          ]}
        />
      )}

      <div className={styles.footnote}>{footnote ?? 'Darker is higher.'}</div>
    </figure>
  );
}
