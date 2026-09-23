import React, {useMemo, useState} from 'react';
import clsx from 'clsx';
import styles from './DiscriminationResults.module.css';
import VendorIcon from '@site/src/components/VendorIcon';
import board from '@site/src/data/results/search-result-discrimination.json';

interface Slice {
  name: string;
  items: number;
  rankable: number;
  ndcg: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  noisePicked: number;
  abstentionAccuracy: number;
  answerAccuracy: number | null;
}

interface Row {
  model: string;
  label: string;
  provider: string;
  isFree: boolean;
  paramsB: number | null;
  scored: number;
  failed: number;
  unparsed: number;
  overall: Slice;
  slices: Slice[];
  groundedRate: number | null;
}

interface Board {
  task: string;
  title: string;
  generated: string;
  taskItems: number;
  sampleItems: number;
  rows: Row[];
}

const DATA = board as unknown as Board;

const SLICES = ['overall', 'web', 'wikipedia', 'no_answer', 'easy', 'medium', 'hard'];

/** A dash where a measure does not apply — never a zero, which is a claim. */
const pct = (value: number | null) =>
  value === null ? '—' : `${(value * 100).toFixed(1)}%`;

function sliceOf(row: Row, name: string): Slice | undefined {
  return name === 'overall' ? row.overall : row.slices.find((s) => s.name === name);
}

export default function DiscriminationResults() {
  const [slice, setSlice] = useState('overall');

  const rows = useMemo(
    () =>
      DATA.rows
        .map((row) => ({row, cells: sliceOf(row, slice)}))
        .filter((entry): entry is {row: Row; cells: Slice} => Boolean(entry.cells))
        .sort((a, b) => b.cells.abstentionAccuracy - a.cells.abstentionAccuracy),
    [slice],
  );

  const partial = DATA.sampleItems < DATA.taskItems;

  return (
    <div className={styles.wrap}>
      {partial && (
        <div className={styles.notice}>
          <strong>A sample, not the task.</strong> Each model was put through{' '}
          {DATA.sampleItems} of the {DATA.taskItems} items, spread evenly across the three
          categories. These numbers are a check that the task runs, not a measurement of
          the field.
        </div>
      )}

      <div className={styles.toolbar}>
        {SLICES.map((name) => (
          <button
            key={name}
            type="button"
            className={clsx(styles.tab, slice === name && styles.tabActive)}
            onClick={() => setSlice(name)}
          >
            {name}
          </button>
        ))}
        <span className={styles.generated}>generated {DATA.generated}</span>
      </div>

      <div className={styles.scroll}>
        <table className={styles.table}>
          <caption className="sr-only">
            {DATA.title}, {slice} slice
          </caption>
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col">Items</th>
              <th scope="col">nDCG@10</th>
              <th scope="col">Precision</th>
              <th scope="col">Recall</th>
              <th scope="col">Noise picked</th>
              <th scope="col">Abstention</th>
              <th scope="col">Answer</th>
              <th scope="col">Failed</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({row, cells}) => (
              <tr key={row.model}>
                <td className={styles.model}>
                  <span className={styles.modelName}>
                    <VendorIcon model={row.model} />
                    {row.label}
                  </span>
                  <span className={styles.modelId}>{row.model}</span>
                </td>
                <td className={styles.numeric}>
                  {cells.items}
                  {cells.rankable !== cells.items && (
                    <span className={styles.muted}> / {cells.rankable} rankable</span>
                  )}
                </td>
                <td className={styles.numeric}>{pct(cells.ndcg)}</td>
                <td className={styles.numeric}>{pct(cells.precision)}</td>
                <td className={styles.numeric}>{pct(cells.recall)}</td>
                <td className={styles.numeric}>{pct(cells.noisePicked)}</td>
                <td className={styles.numeric}>{pct(cells.abstentionAccuracy)}</td>
                <td className={styles.numeric}>{pct(cells.answerAccuracy)}</td>
                <td className={clsx(styles.numeric, row.failed > 0 && styles.warn)}>
                  {row.failed}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.footnote}>
        Sorted by abstention accuracy — on this task set that is the column that
        separates models. <strong>Noise picked</strong> is the share of cited candidates a
        human graded 0. A dash means the measure does not apply: a <code>no_answer</code>
        item has nothing to rank and nothing to recall. <strong>Failed</strong> items
        never returned a reply and are not scored as zero. Groundedness is absent because
        no judge has been run.
      </div>
    </div>
  );
}
