import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import styles from './index.module.css';
import {getRelease, LATEST} from '@site/src/data';
import {pct, usd} from '@site/src/components/charts/format';

function Stat({value, label, note}: {value: string; label: string; note?: string}) {
  return (
    <div className={styles.stat}>
      <div className={styles.statValue}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
      {note && <div className={styles.statNote}>{note}</div>}
    </div>
  );
}

export default function Home() {
  const release = getRelease(LATEST);
  const best = [...release.rows].sort((a, b) => b.accuracy - a.accuracy)[0];
  const cheapest = [...release.rows].sort((a, b) => a.costPer1k - b.costPer1k)[0];

  return (
    <Layout
      title="LLMSearchBench"
      description="A small, reproducible benchmark for how language models use search."
    >
      <header className={styles.hero}>
        <div className="container">
          <div className={styles.eyebrow}>{release.version} · {release.date}</div>
          <h1 className={styles.title}>How well do models actually search?</h1>
          <p className={styles.lede}>
            A small, fully reproducible benchmark measuring retrieval quality, citation
            fidelity, and the cost of getting a grounded answer. Every number on this site
            comes from a versioned run you can re-execute.
          </p>
          <div className={styles.actions}>
            <Link className="button button--primary button--lg" to="/results">
              See the results
            </Link>
            <Link className="button button--secondary button--lg" to="/docs/intro">
              Read the method
            </Link>
          </div>
        </div>
      </header>

      <main className="container">
        <div className={styles.stats}>
          <Stat value={String(release.taskCount)} label="Tasks" note="per model, per run" />
          <Stat value={String(release.rows.length)} label="Models evaluated" />
          <Stat value={pct(best.accuracy)} label="Best accuracy" note={best.model} />
          <Stat value={usd(cheapest.costPer1k)} label="Cheapest / 1k tasks" note={cheapest.model} />
        </div>

        <h2 className={styles.sectionTitle}>Start here</h2>
        <p className={styles.sectionLede}>
          The benchmark is deliberately small: it should run end to end on one machine in
          under an hour, and every claim should be checkable.
        </p>
        <div className={styles.cards}>
          <Link className={styles.card} to="/docs/methodology/tasks">
            <div className={styles.cardTitle}>Task design</div>
            <div className={styles.cardBody}>
              What the {release.taskCount} tasks ask for, and why those and not others.
            </div>
          </Link>
          <Link className={styles.card} to="/docs/methodology/scoring">
            <div className={styles.cardTitle}>Scoring</div>
            <div className={styles.cardBody}>
              The metric definitions, in full, with their formulas.
            </div>
          </Link>
          <Link className={styles.card} to="/docs/reproduce">
            <div className={styles.cardTitle}>Reproduce a run</div>
            <div className={styles.cardBody}>
              Clone, set keys, run one command, diff your numbers against ours.
            </div>
          </Link>
          <Link className={styles.card} to="/docs/versioning">
            <div className={styles.cardTitle}>Versioning policy</div>
            <div className={styles.cardBody}>
              What a benchmark release freezes, and when results stop being comparable.
            </div>
          </Link>
        </div>
      </main>
    </Layout>
  );
}
