import React, {useMemo, useState} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import styles from './DiscriminationIndex.module.css';
import type {DiscriminationItem} from '@site/src/components/DiscriminationExample';

/**
 * Every item whose JSON is on disk.
 *
 * Globbed rather than listed, because half the set is built locally and
 * git-ignored: a published build finds the 120 shippable items, a local one
 * finds all 331, and neither needs a different index file.
 */
interface WebpackContext {
  keys(): string[];
  (id: string): DiscriminationItem;
}

declare const require: NodeRequire & {
  context(path: string, deep: boolean, filter: RegExp): WebpackContext;
};

const context = require.context('@site/src/data/discrimination', false, /\.json$/);
const ITEMS: DiscriminationItem[] = context
  .keys()
  .map((key) => context(key))
  .sort((a, b) => a.id.localeCompare(b.id));

type Sort = 'id' | 'candidates' | 'relevant';

const CATEGORIES = ['all', 'web', 'wikipedia', 'no_answer'] as const;
const TIERS = ['all', 'easy', 'medium', 'hard'] as const;

export default function DiscriminationIndex() {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<string>('all');
  const [tier, setTier] = useState<string>('all');
  const [sort, setSort] = useState<Sort>('id');

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = ITEMS.filter(
      (item) =>
        (category === 'all' || item.category === category) &&
        (tier === 'all' || item.noise_tier === tier) &&
        (!needle ||
          item.id.toLowerCase().includes(needle) ||
          item.question.toLowerCase().includes(needle)),
    );
    return filtered.sort((a, b) => {
      if (sort === 'candidates') return b.candidates.length - a.candidates.length;
      if (sort === 'relevant') return b.supporting_ids.length - a.supporting_ids.length;
      return a.id.localeCompare(b.id);
    });
  }, [query, category, tier, sort]);

  const counts = useMemo(() => {
    const byCategory: Record<string, number> = {};
    for (const item of ITEMS) byCategory[item.category] = (byCategory[item.category] ?? 0) + 1;
    return byCategory;
  }, []);

  const local = (counts.web ?? 0) + (counts.no_answer ?? 0);

  return (
    <div className={styles.wrap}>
      <div className={styles.summary}>
        <div className={styles.stat}>
          <span className={styles.statValue}>{ITEMS.length}</span>
          <span className={styles.statLabel}>items on this machine</span>
        </div>
        {CATEGORIES.slice(1).map((name) => (
          <div key={name} className={styles.stat}>
            <span className={styles.statValue}>{counts[name] ?? 0}</span>
            <span className={styles.statLabel}>{name}</span>
          </div>
        ))}
        <div className={styles.stat}>
          <span className={styles.statValue}>
            {ITEMS.reduce((sum, item) => sum + item.candidates.length, 0)}
          </span>
          <span className={styles.statLabel}>candidates in total</span>
        </div>
      </div>

      {local === 0 && (
        <div className={styles.notice}>
          Only the Wikipedia category is here. The <code>web</code> and{' '}
          <code>no_answer</code> items are built from MS MARCO, which this repository
          may not redistribute — run <code>make tasks-discrimination</code> and{' '}
          <code>llmsearchbench examples-discrimination</code> to read those 211 items on
          your own machine.
        </div>
      )}

      <div className={styles.toolbar}>
        <input
          className={styles.search}
          type="search"
          placeholder="Filter by id or question…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Filter items"
        />
        <select
          className={styles.select}
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          aria-label="Category"
        >
          {CATEGORIES.map((name) => (
            <option key={name} value={name}>
              {name === 'all' ? 'every category' : name}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={tier}
          onChange={(event) => setTier(event.target.value)}
          aria-label="Noise tier"
        >
          {TIERS.map((name) => (
            <option key={name} value={name}>
              {name === 'all' ? 'every tier' : name}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={sort}
          onChange={(event) => setSort(event.target.value as Sort)}
          aria-label="Sort"
        >
          <option value="id">by id</option>
          <option value="candidates">most candidates</option>
          <option value="relevant">most relevant</option>
        </select>
        <span className={styles.count}>{rows.length} shown</span>
      </div>

      <div className={styles.scroll}>
        <table className={styles.table}>
          <caption className="sr-only">Every built discrimination item</caption>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">Category</th>
              <th scope="col">Tier</th>
              <th scope="col">Question</th>
              <th scope="col">Results</th>
              <th scope="col">Relevant</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link to={`/docs/discrimination-examples/${item.id}`}>
                    <code>{item.id}</code>
                  </Link>
                </td>
                <td>
                  <span className={clsx(styles.pill, styles[item.category])}>
                    {item.category}
                  </span>
                </td>
                <td>{item.noise_tier}</td>
                <td className={styles.question} title={item.question}>
                  {item.question}
                </td>
                <td className={styles.numeric}>{item.candidates.length}</td>
                <td className={styles.numeric}>{item.supporting_ids.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
