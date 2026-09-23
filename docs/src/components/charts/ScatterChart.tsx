import React, {useState} from 'react';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';
import {formatters, type Formatter} from './format';

export interface ScatterPoint {
  label: string;
  x: number;
  y: number;
  /** Third measure, drawn as dot area. Optional. */
  size?: number;
  /** Extra tooltip rows, for context that is not on an axis. */
  detail?: Record<string, string>;
}

export interface ScatterChartProps {
  points: ScatterPoint[];
  title: string;
  subtitle?: string;
  xLabel: string;
  yLabel: string;
  xFormat?: keyof typeof formatters | Formatter;
  yFormat?: keyof typeof formatters | Formatter;
  /** Crosshair guides, e.g. a 50/50 split that turns the plot into quadrants. */
  guides?: {x?: number; y?: number};
  /** Text drawn in each corner, read clockwise from top-left. */
  quadrantLabels?: [string, string, string, string];
  /** Legend for the dot-area encoding, when `size` is used. */
  sizeLabel?: string;
  /** Log x axis, for a measure that spans orders of magnitude. */
  xScale?: 'linear' | 'log';
  footnote?: string;
  height?: number;
}

const MIN_R = 4;
const MAX_R = 13;

/**
 * Pad a range so no point sits on the frame.
 *
 * Padding never takes the axis below zero when the data does not go there:
 * a cost axis that starts at -$0.07 reads as though a run could pay you.
 */
function extent(values: number[]): [number, number] {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  if (lo === hi) return [Math.min(lo - 0.5, lo >= 0 ? lo : lo - 0.5), hi + 0.5];
  const pad = (hi - lo) * 0.08;
  return [lo >= 0 ? Math.max(0, lo - pad) : lo - pad, hi + pad];
}

/**
 * Two measures per model, one dot each.
 *
 * A bar chart can rank models on one measure; only a scatter shows *which way*
 * a model is wrong — over-searching and under-searching are different faults
 * with the same accuracy cost.
 */
export default function ScatterChart({
  points,
  title,
  subtitle,
  xLabel,
  yLabel,
  xFormat = 'percent',
  yFormat = 'percent',
  guides,
  quadrantLabels,
  sizeLabel,
  xScale = 'linear',
  footnote,
  height = 420,
}: ScatterChartProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<number | null>(null);

  const fx: Formatter =
    typeof xFormat === 'function' ? xFormat : (formatters[xFormat] ?? formatters.number);
  const fy: Formatter =
    typeof yFormat === 'function' ? yFormat : (formatters[yFormat] ?? formatters.number);

  const padding = {top: 14, right: 18, bottom: 44, left: 62};
  const innerWidth = Math.max(120, width - padding.left - padding.right);
  const innerHeight = height - padding.top - padding.bottom;

  // A log axis is taken in log space throughout, so padding and ticks land
  // where the eye expects rather than bunching at the left.
  const logged = xScale === 'log';
  const fwd = (v: number) => (logged ? Math.log10(Math.max(v, 1e-9)) : v);
  const back = (v: number) => (logged ? 10 ** v : v);

  const [x0, x1] = extent([
    ...points.map((p) => fwd(p.x)),
    ...(guides?.x != null ? [fwd(guides.x)] : []),
  ]);
  const [y0, y1] = extent([...points.map((p) => p.y), ...(guides?.y != null ? [guides.y] : [])]);
  const sx = (v: number) => padding.left + ((fwd(v) - x0) / (x1 - x0)) * innerWidth;
  const sy = (v: number) => padding.top + innerHeight - ((v - y0) / (y1 - y0)) * innerHeight;

  const sizes = points.map((p) => p.size ?? 0);
  const maxSize = Math.max(...sizes, 0);
  const radius = (p: ScatterPoint) =>
    p.size == null || maxSize === 0
      ? MIN_R + 1
      : MIN_R + Math.sqrt(p.size / maxSize) * (MAX_R - MIN_R);

  const ticks = (lo: number, hi: number) =>
    [0, 0.25, 0.5, 0.75, 1].map((t) => lo + t * (hi - lo));

  // Only the extremes are labelled: with thirty models, labelling every dot
  // would produce a solid block of text and no readable chart.
  const named = new Set<number>();
  for (const pick of [
    (a: ScatterPoint, b: ScatterPoint) => b.x - a.x,
    (a: ScatterPoint, b: ScatterPoint) => a.x - b.x,
    (a: ScatterPoint, b: ScatterPoint) => b.y - a.y,
    (a: ScatterPoint, b: ScatterPoint) => a.y - b.y,
  ]) {
    const best = points.indexOf([...points].sort(pick)[0]);
    if (best >= 0) named.add(best);
  }

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
        aria-label={`${title}. ${points
          .map((p) => `${p.label}: ${xLabel} ${fx(p.x)}, ${yLabel} ${fy(p.y)}`)
          .join('; ')}`}
        onMouseLeave={() => setHover(null)}
      >
        {ticks(y0, y1).map((t, i) => (
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
        {ticks(x0, x1).map((t, i) => (
          <text
            key={`x${i}`}
            className={styles.axisLabel}
            x={sx(back(t))}
            y={padding.top + innerHeight + 16}
            textAnchor="middle"
          >
            {fx(back(t))}
          </text>
        ))}

        {guides?.x != null && (
          <line
            className={styles.guide}
            x1={sx(guides.x)}
            x2={sx(guides.x)}
            y1={padding.top}
            y2={padding.top + innerHeight}
          />
        )}
        {guides?.y != null && (
          <line
            className={styles.guide}
            x1={padding.left}
            x2={padding.left + innerWidth}
            y1={sy(guides.y)}
            y2={sy(guides.y)}
          />
        )}

        {quadrantLabels && (
          <>
            <text className={styles.quadrant} x={padding.left + 8} y={padding.top + 14}>
              {quadrantLabels[0]}
            </text>
            <text
              className={styles.quadrant}
              x={padding.left + innerWidth - 8}
              y={padding.top + 14}
              textAnchor="end"
            >
              {quadrantLabels[1]}
            </text>
            <text
              className={styles.quadrant}
              x={padding.left + innerWidth - 8}
              y={padding.top + innerHeight - 6}
              textAnchor="end"
            >
              {quadrantLabels[2]}
            </text>
            <text
              className={styles.quadrant}
              x={padding.left + 8}
              y={padding.top + innerHeight - 6}
            >
              {quadrantLabels[3]}
            </text>
          </>
        )}

        <line
          className={styles.axis}
          x1={padding.left}
          x2={padding.left}
          y1={padding.top}
          y2={padding.top + innerHeight}
        />
        <line
          className={styles.axis}
          x1={padding.left}
          x2={padding.left + innerWidth}
          y1={padding.top + innerHeight}
          y2={padding.top + innerHeight}
        />

        {points.map((point, i) => (
          <g key={point.label} onMouseEnter={() => setHover(i)}>
            <circle
              cx={sx(point.x)}
              cy={sy(point.y)}
              r={radius(point) + 6}
              className={styles.hit}
            />
            <circle
              cx={sx(point.x)}
              cy={sy(point.y)}
              r={radius(point)}
              fill="var(--series-1)"
              stroke="var(--lsb-surface)"
              strokeWidth={2}
              opacity={hover === null || hover === i ? 0.85 : 0.35}
            />
            {(named.has(i) || hover === i) && (
              <text
                className={styles.pointLabel}
                x={sx(point.x) + radius(point) + 5}
                y={sy(point.y)}
                dominantBaseline="central"
              >
                {point.label}
              </text>
            )}
          </g>
        ))}

        <text
          className={styles.axisTitle}
          x={padding.left + innerWidth / 2}
          y={height - 6}
          textAnchor="middle"
        >
          {xLabel}
        </text>
        <text
          className={styles.axisTitle}
          transform={`translate(13 ${padding.top + innerHeight / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          {yLabel}
        </text>
      </svg>

      {hover !== null && (
        <Tooltip
          x={Math.min(sx(points[hover].x) + 14, width - 150)}
          y={sy(points[hover].y) + (subtitle ? 74 : 54)}
          title={points[hover].label}
          rows={[
            {label: xLabel, value: fx(points[hover].x), color: 'var(--series-1)'},
            {label: yLabel, value: fy(points[hover].y)},
            ...(points[hover].size != null && sizeLabel
              ? [{label: sizeLabel, value: formatters.percent(points[hover].size as number)}]
              : []),
            ...Object.entries(points[hover].detail ?? {}).map(([label, value]) => ({
              label,
              value,
            })),
          ]}
        />
      )}

      <div className={styles.footnote}>
        {footnote ?? 'Hover a dot for the model behind it.'}
        {sizeLabel && ` Dot area is ${sizeLabel.toLowerCase()}.`}
      </div>
    </figure>
  );
}
