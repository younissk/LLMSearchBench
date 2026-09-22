import React, {useMemo, useState} from 'react';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';
import {formatters, type Formatter} from './format';

export interface ScatterPoint {
  label: string;
  x: number;
  y: number;
  group: string;
}

/**
 * Scatter compares every pair of colours at once, so the palette is capped at
 * three validated slots (all-pairs CVD ΔE 9.2 light / 9.4 dark); anything past
 * the third group folds into a neutral "Other".
 */
const ALL_PAIRS_SLOTS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)'];
const OTHER = 'var(--lsb-ink-muted)';
const OTHER_LABEL = 'Other';

export interface ScatterPlotProps {
  data: ScatterPoint[];
  title: string;
  subtitle?: string;
  xLabel: string;
  yLabel: string;
  xFormat?: keyof typeof formatters | Formatter;
  yFormat?: keyof typeof formatters | Formatter;
  /** Log-scale the x axis — right for cost, which spans orders of magnitude. */
  logX?: boolean;
  /** Direct-label this many top points by y. */
  labelTop?: number;
  footnote?: string;
}

const HEIGHT = 380;
const MARKER = 5; // radius -> 10px mark, above the 8px floor

export default function ScatterPlot({
  data,
  title,
  subtitle,
  xLabel,
  yLabel,
  xFormat = 'number',
  yFormat = 'number',
  logX = false,
  labelTop = 3,
  footnote,
}: ScatterPlotProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<number | null>(null);

  const fx: Formatter =
    typeof xFormat === 'function' ? xFormat : (formatters[xFormat] ?? formatters.number);
  const fy: Formatter =
    typeof yFormat === 'function' ? yFormat : (formatters[yFormat] ?? formatters.number);

  const groups = useMemo(() => {
    const seen = Array.from(new Set(data.map((d) => d.group)));
    return seen.length <= 3 ? seen : [...seen.slice(0, 3), OTHER_LABEL];
  }, [data]);

  const colorOf = (group: string) => {
    const i = groups.indexOf(group);
    return i >= 0 && i < 3 ? ALL_PAIRS_SLOTS[i] : OTHER;
  };
  const groupOf = (group: string) => (groups.indexOf(group) >= 0 ? group : OTHER_LABEL);

  const padding = {top: 10, right: 20, bottom: 46, left: 58};
  const innerWidth = Math.max(120, width - padding.left - padding.right);
  const innerHeight = HEIGHT - padding.top - padding.bottom;

  const tx = (v: number) => (logX ? Math.log10(Math.max(v, 1e-3)) : v);
  const xs = data.map((d) => tx(d.x));
  const ys = data.map((d) => d.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const yPad = (yMax - yMin) * 0.12 || 0.05;
  const xPad = (xMax - xMin) * 0.08 || 0.5;

  const sx = (v: number) =>
    padding.left + ((tx(v) - (xMin - xPad)) / (xMax + xPad - (xMin - xPad))) * innerWidth;
  const sy = (v: number) =>
    padding.top + innerHeight - ((v - (yMin - yPad)) / (yMax + yPad - (yMin - yPad))) * innerHeight;

  const yTicks = Array.from({length: 5}, (_, i) => yMin - yPad + ((yMax + yPad - (yMin - yPad)) * i) / 4);
  const xTicks = Array.from({length: 5}, (_, i) => {
    const t = xMin - xPad + ((xMax + xPad - (xMin - xPad)) * i) / 4;
    return logX ? Math.pow(10, t) : t;
  });

  const topIdx = new Set(
    [...data.keys()].sort((a, b) => data[b].y - data[a].y).slice(0, labelTop),
  );

  return (
    <figure className={styles.figure} ref={ref}>
      <figcaption className={styles.caption}>
        <div className={styles.title}>{title}</div>
        {subtitle && <div className={styles.subtitle}>{subtitle}</div>}
      </figcaption>

      <svg
        className={styles.plot}
        width={width}
        height={HEIGHT}
        role="img"
        aria-label={`${title}. ${data
          .map((d) => `${d.label}: ${xLabel} ${fx(d.x)}, ${yLabel} ${fy(d.y)}`)
          .join('. ')}`}
        onMouseLeave={() => setHover(null)}
      >
        {yTicks.map((t, i) => (
          <g key={`y${i}`}>
            <line
              className={styles.grid}
              x1={padding.left}
              x2={padding.left + innerWidth}
              y1={sy(t)}
              y2={sy(t)}
            />
            <text
              className={styles.axisLabel}
              x={padding.left - 8}
              y={sy(t)}
              textAnchor="end"
              dominantBaseline="central"
            >
              {fy(t)}
            </text>
          </g>
        ))}

        <line
          className={styles.axis}
          x1={padding.left}
          x2={padding.left + innerWidth}
          y1={padding.top + innerHeight}
          y2={padding.top + innerHeight}
        />

        {xTicks.map((t, i) => (
          <text
            key={`x${i}`}
            className={styles.axisLabel}
            x={sx(t)}
            y={padding.top + innerHeight + 18}
            textAnchor="middle"
          >
            {fx(t)}
          </text>
        ))}

        <text
          className={styles.axisLabel}
          x={padding.left + innerWidth / 2}
          y={HEIGHT - 6}
          textAnchor="middle"
        >
          {xLabel}
        </text>
        <text
          className={styles.axisLabel}
          transform={`translate(14 ${padding.top + innerHeight / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          {yLabel}
        </text>

        {data.map((d, i) => {
          const active = hover === i;
          return (
            <g key={d.label} onMouseEnter={() => setHover(i)}>
              {/* hit target larger than the mark */}
              <circle className={styles.hit} cx={sx(d.x)} cy={sy(d.y)} r={16} />
              <circle
                cx={sx(d.x)}
                cy={sy(d.y)}
                r={active ? MARKER + 1.5 : MARKER}
                fill={colorOf(groupOf(d.group))}
                stroke="var(--lsb-surface)"
                strokeWidth={2}
                opacity={hover === null || active ? 1 : 0.5}
              />
              {(topIdx.has(i) || active) && (
                <text
                  className={styles.categoryLabel}
                  x={sx(d.x)}
                  y={sy(d.y) - 12}
                  textAnchor="middle"
                >
                  {d.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div className={styles.legend}>
        {groups.map((g) => (
          <span key={g} className={styles.legendItem}>
            <span className={styles.legendSwatch} style={{background: colorOf(g)}} />
            {g}
          </span>
        ))}
      </div>

      {hover !== null && (
        <Tooltip
          x={sx(data[hover].x)}
          y={sy(data[hover].y) + (subtitle ? 74 : 54)}
          title={data[hover].label}
          rows={[
            {label: 'Group', value: data[hover].group, color: colorOf(groupOf(data[hover].group))},
            {label: xLabel, value: fx(data[hover].x)},
            {label: yLabel, value: fy(data[hover].y)},
          ]}
        />
      )}

      {footnote && <div className={styles.footnote}>{footnote}</div>}
    </figure>
  );
}
