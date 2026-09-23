import React, {useMemo, useState} from 'react';
import clsx from 'clsx';
import styles from './Leaderboard.module.css';
import VendorIcon from '@site/src/components/VendorIcon';
import {getLeaderboard, type LeaderboardRow} from '@site/src/data';

type Direction = 'higher' | 'lower';

interface Column {
  key: keyof LeaderboardRow;
  header: string;
  /** Which direction counts as better, for the ✓ marker. */
  better?: Direction;
  format: (row: LeaderboardRow) => string;
}

const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

const COLUMNS: Column[] = [
  {key: 'label', header: 'Model', format: (row) => row.label},
  {
    key: 'decisionAccuracy',
    header: 'Decision',
    better: 'higher',
    format: (row) => pct(row.decisionAccuracy),
  },
  {
    key: 'memoryAccuracy',
    header: 'memory',
    better: 'higher',
    format: (row) => pct(row.memoryAccuracy),
  },
  {
    key: 'searchAccuracy',
    header: 'search',
    better: 'higher',
    format: (row) => pct(row.searchAccuracy),
  },
  {
    key: 'noToolAccuracy',
    header: 'no_tool',
    better: 'higher',
    format: (row) => pct(row.noToolAccuracy),
  },
  {
    key: 'adversarialAccuracy',
    header: 'Traps',
    better: 'higher',
    format: (row) => pct(row.adversarialAccuracy),
  },
  {
    key: 'wellFormedRate',
    header: 'Calls OK',
    better: 'higher',
    format: (row) => pct(row.wellFormedRate),
  },
  {
    key: 'costUsd',
    header: 'Cost',
    better: 'lower',
    format: (row) => (row.isFree ? 'free' : `$${row.costUsd.toFixed(3)}`),
  },
];

export interface LeaderboardProps {
  /** Task id, e.g. `tool-use-correctness`. */
  task: string;
  /** Hide the search box for an embedded, compact view. */
  compact?: boolean;
}

export default function Leaderboard({task, compact = false}: LeaderboardProps) {
  const board = getLeaderboard(task);
  const [sortKey, setSortKey] = useState<keyof LeaderboardRow>('decisionAccuracy');
  const [desc, setDesc] = useState(true);
  const [query, setQuery] = useState('');

  const best = useMemo(() => {
    const out: Partial<Record<keyof LeaderboardRow, number>> = {};
    for (const column of COLUMNS) {
      if (!column.better) continue;
      // A partial run is not comparable, so it cannot hold a best-in-column.
      const values = board.rows
        .filter((row) => row.complete)
        .map((row) => row[column.key] as number);
      if (!values.length) continue;
      out[column.key] =
        column.better === 'higher' ? Math.max(...values) : Math.min(...values);
    }
    return out;
  }, [board]);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return board.rows
      .filter(
        (row) =>
          !needle ||
          row.label.toLowerCase().includes(needle) ||
          row.model.toLowerCase().includes(needle),
      )
      .slice()
      .sort((a, b) => {
        const x = a[sortKey];
        const y = b[sortKey];
        const cmp =
          typeof x === 'number' && typeof y === 'number'
            ? x - y
            : String(x).localeCompare(String(y));
        return desc ? -cmp : cmp;
      });
  }, [board, query, sortKey, desc]);

  const onSort = (key: keyof LeaderboardRow) => {
    if (key === sortKey) {
      setDesc((value) => !value);
    } else {
      setSortKey(key);
      setDesc(true);
    }
  };

  const anyPartial = board.rows.some((row) => !row.complete);

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        {!compact && (
          <input
            className={styles.search}
            type="search"
            placeholder="Filter models…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Filter models"
          />
        )}
        <span>
          {rows.length} model{rows.length === 1 ? '' : 's'} · {board.taskItems} items ·
          generated {board.generated}
        </span>
      </div>

      <div className={styles.scroll}>
        <table className={styles.table}>
          <caption className="sr-only">
            {board.title} leaderboard, {board.taskItems} items
          </caption>
          <thead>
            <tr>
              {COLUMNS.map((column) => {
                const active = sortKey === column.key;
                return (
                  <th
                    key={String(column.key)}
                    scope="col"
                    aria-sort={active ? (desc ? 'descending' : 'ascending') : 'none'}
                  >
                    <button
                      type="button"
                      className={styles.sortButton}
                      onClick={() => onSort(column.key)}
                    >
                      {column.header}
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
                {COLUMNS.map((column) => {
                  const isModel = column.key === 'label';
                  const value = row[column.key];
                  const isBest =
                    row.complete &&
                    typeof value === 'number' &&
                    best[column.key] === value;
                  return (
                    <td
                      key={String(column.key)}
                      className={clsx(
                        !isModel && styles.numeric,
                        isModel && styles.model,
                        isBest && styles.best,
                      )}
                    >
                      {isModel ? (
                        <span className={styles.modelName}>
                          <VendorIcon model={row.model} />
                          {row.label}
                        </span>
                      ) : (
                        column.format(row)
                      )}
                      {isModel && <span className={styles.modelId}>{row.model}</span>}
                      {isModel && !row.complete && (
                        <span className={styles.partial} title="run did not finish">
                          {' '}
                          partial ({row.items}/{board.taskItems})
                        </span>
                      )}
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
      </div>

      <div className={styles.footnote}>
        <strong>memory</strong>, <strong>search</strong> and <strong>no_tool</strong> are
        the share of right search-or-not decisions in each bucket.{' '}
        <strong>Traps</strong> is decision accuracy on items worded to bait a search.{' '}
        <strong>Calls OK</strong> is the share of calling items with a well-formed call.
        {anyPartial && ' A partial run cannot hold a best-in-column mark.'}
      </div>
    </div>
  );
}
