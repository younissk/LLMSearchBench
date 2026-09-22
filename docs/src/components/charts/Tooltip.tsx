import React from 'react';
import styles from './Tooltip.module.css';

export interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

export function Tooltip({
  x,
  y,
  title,
  rows,
}: {
  x: number;
  y: number;
  title: string;
  rows: TooltipRow[];
}) {
  return (
    <div className={styles.tooltip} style={{left: x, top: y}} role="presentation">
      <div className={styles.title}>{title}</div>
      {rows.map((row) => (
        <div key={row.label} className={styles.row}>
          <span>
            {row.color && (
              <span className={styles.swatch} style={{background: row.color}} />
            )}
            {row.label}
          </span>
          <span className={styles.value}>{row.value}</span>
        </div>
      ))}
    </div>
  );
}
