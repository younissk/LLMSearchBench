import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import styles from './index.module.css';
import {getLeaderboard} from '@site/src/data';
import {pct} from '@site/src/components/charts/format';

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
  const board = getLeaderboard('tool-use-correctness');
  const ranked = [...board.rows].sort(
    (a, b) => b.decisionAccuracy - a.decisionAccuracy,
  );
  const best = ranked[0];

  return (
    <Layout
      title="LLMSearchBench"
      description="A small, reproducible benchmark for how language models use search."
    >
      <header className={styles.hero}>
        <div className="container">
          <div className={styles.eyebrow}>updated {board.generated}</div>
          <h1 className={styles.title}>Does the model know when to search?</h1>
          <p className={styles.lede}>
            A small, fully reproducible benchmark. Give a model a search tool, then
            measure whether it reaches for it at the right moments — and whether it
            calls it properly when it does.
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
          <Stat value={String(board.taskItems)} label="Prompts" note="per model, per run" />
          <Stat value={String(board.rows.length)} label="Models run" />
          <Stat
            value={best ? pct(best.decisionAccuracy) : '—'}
            label="Best decision accuracy"
            note={best?.label}
          />
          <Stat
            value={best ? pct(best.memoryAccuracy) : '—'}
            label="…of which on known facts"
            note="where models struggle most"
          />
        </div>

        <h2 className={styles.sectionTitle}>Start here</h2>
        <p className={styles.sectionLede}>
          The benchmark is deliberately small: a full run costs cents and finishes in
          minutes, so every number here can be re-checked rather than trusted.
        </p>
        <div className={styles.cards}>
          <Link className={styles.card} to="/docs/tasks/tool-use-correctness/buckets">
            <div className={styles.cardTitle}>The three kinds of prompt</div>
            <div className={styles.cardBody}>
              What the {board.taskItems} prompts look like, and why each one is there.
            </div>
          </Link>
          <Link className={styles.card} to="/docs/tasks/tool-use-correctness/metrics">
            <div className={styles.cardTitle}>What we measure</div>
            <div className={styles.cardBody}>
              Three scores, kept separate, with a worked example.
            </div>
          </Link>
          <Link className={styles.card} to="/docs/tasks/tool-use-correctness/running">
            <div className={styles.cardTitle}>Run it yourself</div>
            <div className={styles.cardBody}>
              One key, two commands. A short run costs cents.
            </div>
          </Link>
          <Link className={styles.card} to="/docs/tasks/tool-use-correctness/qwen-coverage">
            <div className={styles.cardTitle}>Model coverage</div>
            <div className={styles.cardBody}>
              Which models have been run, and which are still on the list.
            </div>
          </Link>
        </div>
      </main>
    </Layout>
  );
}
