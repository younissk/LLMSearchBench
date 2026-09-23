import React, {useMemo, useState} from 'react';
import clsx from 'clsx';
import styles from './DiscriminationResults.module.css';
import VendorIcon from '@site/src/components/VendorIcon';
import board from '@site/src/data/results/search-result-discrimination.json';

interface Slice {
  name: string;
  items: number;
  correct: number;
  accuracy: number;
}

interface Row {
  model: string;
  label: string;
  provider: string;
  isFree: boolean;
  paramsB: number | null;
  scored: number;
  failed: number;
  fabricated: number;
  wronglyRefused: number;
  overall: Slice;
  slices: Slice[];
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

const SLICES = ['overall', 'wikipedia', 'no_answer', 'easy', 'medium', 'hard'];

const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

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
        .sort((a, b) => b.cells.accuracy - a.cells.accuracy),
    [slice],
  );

  const partial = DATA.sampleItems < DATA.taskItems;

  return (
    <div className={styles.wrap}>
      {partial && (
        <div className={styles.notice}>
          <strong>A sample, not the task.</strong> Each model was put through{' '}
          {DATA.sampleItems} of the {DATA.taskItems} scorable items, spread evenly across
          the categories. A check that the task runs, not a measurement of the field.
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
              <th scope="col">Correct</th>
              <th scope="col">Accuracy</th>
              <th scope="col">Answered anyway</th>
              <th scope="col">Refused wrongly</th>
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
                <td className={styles.numeric}>{cells.items}</td>
                <td className={styles.numeric}>{cells.correct}</td>
                <td className={styles.numeric}>{pct(cells.accuracy)}</td>
                <td className={styles.numeric}>{row.fabricated}</td>
                <td className={styles.numeric}>{row.wronglyRefused}</td>
                <td className={clsx(styles.numeric, row.failed > 0 && styles.warn)}>
                  {row.failed}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.footnote}>
        One question per item: was the answer right? Where the results carry the answer,
        right means giving it; where they do not, right means saying so.{' '}
        <strong>Answered anyway</strong> counts items whose results had no answer and got
        one regardless — true or not, it did not come from the results.{' '}
        <strong>Refused wrongly</strong> is the opposite mistake. Both are whole-run
        counts, not per slice. <strong>Failed</strong> items never returned a reply and
        are not scored as wrong.
      </div>
    </div>
  );
}
