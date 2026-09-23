import React, {useState} from 'react';
import styles from './chart.module.css';
import {Tooltip} from './Tooltip';
import {useChartWidth} from './useChartWidth';

export interface HistogramBin {
  label: string;
  count: number;
  /** Anything worth showing on hover, e.g. an example item. */
  detail?: string;
}

export interface HistogramChartProps {
  bins: HistogramBin[];
  title: string;
  subtitle?: string;
  xLabel: string;
  yLabel: string;
  footnote?: string;
  height?: number;
}

const GAP = 2;

/** A distribution, drawn vertically because the x axis is ordered. */
export default function HistogramChart({
  bins,
  title,
  subtitle,
  xLabel,
  yLabel,
  footnote,
  height = 300,
}: HistogramChartProps) {
  const {ref, width} = useChartWidth();
  const [hover, setHover] = useState<number | null>(null);

  const padding = {top: 10, right: 12, bottom: 48, left: 46};
  const innerWidth = Math.max(60, width - padding.left - padding.right);
  const innerHeight = height - padding.top - padding.bottom;
  const slot = innerWidth / Math.max(bins.length, 1);

  const max = Math.max(...bins.map((b) => b.count), 1);
  const sy = (v: number) => padding.top + innerHeight - (v / max) * innerHeight;

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
        aria-label={`${title}. ${bins.map((b) => `${b.label}: ${b.count}`).join(', ')}`}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 0.5, 1].map((t) => (
          <g key={t}>
            <line
              className={styles.grid}
              x1={padding.left}
              x2={padding.left + innerWidth}
              y1={sy(t * max)}
              y2={sy(t * max)}
            />
            <text
              className={styles.axisLabel}
              x={padding.left - 8}
              y={sy(t * max)}
              textAnchor="end"
              dominantBaseline="central"
            >
              {Math.round(t * max)}
            </text>
          </g>
        ))}

        {bins.map((bin, i) => {
          const x = padding.left + i * slot;
          const y = sy(bin.count);
          return (
            <g key={bin.label} onMouseEnter={() => setHover(i)}>
              <rect
                className={styles.hit}
                x={x}
                y={padding.top}
                width={slot}
                height={innerHeight}
              />
              <rect
                x={x + GAP / 2}
                y={y}
                width={Math.max(slot - GAP, 1)}
                height={Math.max(padding.top + innerHeight - y, bin.count ? 1 : 0)}
                rx={3}
                fill="var(--series-1)"
                opacity={hover === null || hover === i ? 1 : 0.4}
              />
              {(i === 0 || i === bins.length - 1 || i % Math.ceil(bins.length / 10) === 0) && (
                <text
                  className={styles.axisLabel}
                  x={x + slot / 2}
                  y={padding.top + innerHeight + 16}
                  textAnchor="middle"
                >
                  {bin.label}
                </text>
              )}
            </g>
          );
        })}

        <line
          className={styles.axis}
          x1={padding.left}
          x2={padding.left + innerWidth}
          y1={padding.top + innerHeight}
          y2={padding.top + innerHeight}
        />
        <text
          className={styles.axisTitle}
          x={padding.left + innerWidth / 2}
          y={height - 8}
          textAnchor="middle"
        >
          {xLabel}
        </text>
        <text
          className={styles.axisTitle}
          transform={`translate(12 ${padding.top + innerHeight / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          {yLabel}
        </text>
      </svg>

      {hover !== null && (
        <Tooltip
          x={Math.min(padding.left + hover * slot + slot, width - 170)}
          y={sy(bins[hover].count) + (subtitle ? 70 : 50)}
          title={bins[hover].label}
          rows={[
            {label: yLabel, value: String(bins[hover].count), color: 'var(--series-1)'},
            ...(bins[hover].detail ? [{label: 'Example', value: bins[hover].detail!}] : []),
          ]}
        />
      )}

      <div className={styles.footnote}>{footnote ?? ''}</div>
    </figure>
  );
}
