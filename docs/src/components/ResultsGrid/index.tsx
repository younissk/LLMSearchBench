import React, {useMemo, useState} from 'react';
import clsx from 'clsx';
import styles from './ResultsGrid.module.css';
import {getRelease, LATEST} from '@site/src/data';
import type {ResultRow} from '@site/src/data/types';
import {formatters, type Formatter} from '@site/src/components/charts/format';

export interface Column {
  key: keyof ResultRow;
  header: string;
  format?: keyof typeof formatters | Formatter;
  /** Direction that counts as "best" for the ✓ marker. */
  better?: 'higher' | 'lower' | 'none';
}

export const DEFAULT_COLUMNS: Column[] = [
  {key: 'model', header: 'Model', better: 'none'},
  {key: 'provider', header: 'Provider', better: 'none'},
  {key: 'accuracy', header: 'Accuracy', format: 'percent', better: 'higher'},
  {key: 'citationF1', header: 'Citation F1', format: 'percent', better: 'higher'},
  {key: 'hallucinationRate', header: 'Hallucination', format: 'percent', better: 'lower'},
  {key: 'latencyP50', header: 'Latency p50', format: 'seconds', better: 'lower'},
  {key: 'costPer1k', header: 'Cost / 1k', format: 'usd', better: 'lower'},
  {key: 'searchCalls', header: 'Search calls', format: 'number', better: 'none'},
];

export interface ResultsGridProps {
  /** Benchmark release to render. Defaults to the latest. */
  release?: string;
  columns?: Column[];
  /** Column sorted on first render. */
  initialSort?: keyof ResultRow;
  /** Hide the search box and provider filter. */
  compact?: boolean;
}

function resolve(col: Column): Formatter | null {
  if (!col.format) return null;
  return typeof col.format === 'function' ? col.format : (formatters[col.format] ?? null);
}

function toCsv(rows: ResultRow[], columns: Column[]): string {
  const head = columns.map((c) => c.header).join(',');
  const body = rows.map((r) =>
    columns
      .map((c) => {
        const v = r[c.key];
        return typeof v === 'string' && v.includes(',') ? `"${v}"` : String(v);
      })
      .join(','),
  );
  return [head, ...body].join('\n');
}

export default function ResultsGrid({
  release = LATEST,
  columns = DEFAULT_COLUMNS,
  initialSort = 'accuracy',
  compact = false,
}: ResultsGridProps) {
  const data = getRelease(release);
  const [sortKey, setSortKey] = useState<keyof ResultRow>(initialSort);
  const [desc, setDesc] = useState(true);
  const [query, setQuery] = useState('');
  const [provider, setProvider] = useState('all');

  const providers = useMemo(
    () => Array.from(new Set(data.rows.map((r) => r.provider))).sort(),
    [data],
  );

  const best = useMemo(() => {
    const out: Partial<Record<keyof ResultRow, number>> = {};
    for (const col of columns) {
      if (!col.better || col.better === 'none') continue;
      const values = data.rows.map((r) => r[col.key] as number);
      out[col.key] = col.better === 'higher' ? Math.max(...values) : Math.min(...values);
    }
    return out;
  }, [data, columns]);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return data.rows
      .filter((r) => provider === 'all' || r.provider === provider)
      .filter(
        (r) =>
          !needle ||
          r.model.toLowerCase().includes(needle) ||
          r.provider.toLowerCase().includes(needle),
      )
      .sort((a, b) => {
        const x = a[sortKey];
        const y = b[sortKey];
        const cmp =
          typeof x === 'number' && typeof y === 'number'
            ? x - y
            : String(x).localeCompare(String(y));
        return desc ? -cmp : cmp;
      });
  }, [data, query, provider, sortKey, desc]);

  const onSort = (key: keyof ResultRow) => {
    if (key === sortKey) {
      setDesc((d) => !d);
    } else {
      setSortKey(key);
      setDesc(true);
    }
  };

  const download = () => {
    const blob = new Blob([toCsv(rows, columns)], {type: 'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `llmsearchbench-${release}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        {!compact && (
          <>
            <input
              className={styles.search}
              type="search"
              placeholder="Filter models…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Filter models"
            />
            <select
              className={styles.select}
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              aria-label="Filter by provider"
            >
              <option value="all">All providers</option>
              {providers.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </>
        )}
        <span className={styles.count}>
          {rows.length} / {data.rows.length} models · {release} · {data.taskCount} tasks
        </span>
        <button type="button" className={styles.button} onClick={download}>
          Download CSV
        </button>
      </div>

      <div className={styles.scroll}>
        <table className={styles.table}>
          <caption className="sr-only">
            LLMSearchBench {release} results, {data.taskCount} tasks
          </caption>
          <thead>
            <tr>
              {columns.map((col) => {
                const active = sortKey === col.key;
                return (
                  <th
                    key={String(col.key)}
                    scope="col"
                    aria-sort={active ? (desc ? 'descending' : 'ascending') : 'none'}
                  >
                    <button
                      type="button"
                      className={styles.sortButton}
                      onClick={() => onSort(col.key)}
                    >
                      {col.header}
                      <span className={clsx(styles.caret, active && styles.caretActive)}>
                        {active ? (desc ? '▼' : '▲') : '▽'}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.model}>
                {columns.map((col) => {
                  const value = row[col.key];
                  const fmt = resolve(col);
                  const isBest =
                    typeof value === 'number' && best[col.key] === value;
                  return (
                    <td
                      key={String(col.key)}
                      className={clsx(
                        typeof value === 'number' && styles.numeric,
                        col.key === 'model' && styles.model,
                        col.key === 'provider' && styles.provider,
                        isBest && styles.best,
                      )}
                    >
                      {typeof value === 'number' && fmt ? fmt(value) : String(value)}
                      {isBest && (
                        <span className={styles.bestMark} title="Best in column">
                          ✓
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <div className={styles.empty}>No models match that filter.</div>}
      </div>
    </div>
  );
}
