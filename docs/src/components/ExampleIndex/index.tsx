import React, {useMemo, useState} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import styles from './ExampleIndex.module.css';
import {getItemMatrix, isCorrect} from '@site/src/data/charts';

type Sort = 'id' | 'accuracy' | 'bucket';

/**
 * Every task item, with how much of the field got it right.
 *
 * Sorted by accuracy ascending by default: the items at the top are the ones
 * worth reading, either because they are genuinely hard or because they are
 * labelled wrong.
 */
export default function ExampleIndex({task}: {task: string}) {
  const matrix = getItemMatrix(task);
  const [query, setQuery] = useState('');
  const [bucket, setBucket] = useState<string>('all');
  const [sort, setSort] = useState<Sort>('accuracy');

  const scored = useMemo(
    () =>
      matrix.items.map((item, i) => {
        const right = matrix.models.filter((model) => isCorrect(model, i)).length;
        const searched = matrix.models.filter(
          (model) => model.decisions[i] === 'S' || model.decisions[i] === 'O',
        ).length;
        return {
          item,
          right,
          searched,
          accuracy: matrix.models.length ? right / matrix.models.length : 0,
        };
      }),
    [matrix],
  );

  const average = scored.length
    ? scored.reduce((sum, row) => sum + row.accuracy, 0) / scored.length
    : 0;

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = scored.filter(
      ({item}) =>
        (bucket === 'all' || item.bucket === bucket) &&
        (!needle ||
          item.id.toLowerCase().includes(needle) ||
          item.subcategory.toLowerCase().includes(needle)),
    );
    return filtered.sort((a, b) => {
      if (sort === 'accuracy') return a.accuracy - b.accuracy || a.item.id.localeCompare(b.item.id);
      if (sort === 'bucket')
        return a.item.bucket.localeCompare(b.item.bucket) || a.accuracy - b.accuracy;
      return a.item.id.localeCompare(b.item.id);
    });
  }, [scored, query, bucket, sort]);

  const buckets = ['all', 'memory', 'search', 'no_tool'];

  return (
    <div className={styles.wrap}>
      <div className={styles.summary}>
        <div className={styles.stat}>
          <span className={styles.statValue}>{(average * 100).toFixed(1)}%</span>
          <span className={styles.statLabel}>average accuracy across all items</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>{matrix.items.length}</span>
          <span className={styles.statLabel}>items</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>{matrix.models.length}</span>
          <span className={styles.statLabel}>complete runs</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>
            {scored.filter((row) => row.right === 0).length}
          </span>
          <span className={styles.statLabel}>items nobody got right</span>
        </div>
      </div>

      <div className={styles.toolbar}>
        <input
          className={styles.search}
          type="search"
          placeholder="Filter by id or subcategory…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Filter items"
        />
        <select
          className={styles.select}
          value={bucket}
          onChange={(event) => setBucket(event.target.value)}
          aria-label="Bucket"
        >
          {buckets.map((value) => (
            <option key={value} value={value}>
              {value === 'all' ? 'every bucket' : value}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={sort}
          onChange={(event) => setSort(event.target.value as Sort)}
          aria-label="Sort"
        >
          <option value="accuracy">hardest first</option>
          <option value="bucket">by bucket</option>
          <option value="id">by id</option>
        </select>
        <span className={styles.count}>{rows.length} shown</span>
      </div>

      <div className={styles.scroll}>
        <table className={styles.table}>
          <caption className="sr-only">
            Every task item with the share of models that decided it correctly
          </caption>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">Bucket</th>
              <th scope="col">Subcategory</th>
              <th scope="col">Models right</th>
              <th scope="col">Accuracy</th>
              <th scope="col">Searched</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({item, right, searched, accuracy}) => (
              <tr key={item.id}>
                <td>
                  <Link to={`/docs/examples/${item.id}`}>
                    <code>{item.id}</code>
                  </Link>
                  {item.adversarial && <span className={styles.trap}>trap</span>}
                </td>
                <td>{item.bucket}</td>
                <td>{item.subcategory}</td>
                <td className={styles.numeric}>
                  {right}/{matrix.models.length}
                </td>
                <td className={styles.numeric}>
                  <span
                    className={clsx(
                      styles.bar,
                      accuracy === 0 && styles.barEmpty,
                    )}
                    style={{'--fill': `${accuracy * 100}%`} as React.CSSProperties}
                  />
                  {(accuracy * 100).toFixed(0)}%
                </td>
                <td className={styles.numeric}>{searched}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
