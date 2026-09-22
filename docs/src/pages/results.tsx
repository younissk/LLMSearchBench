import React, {useState} from 'react';
import Layout from '@theme/Layout';
import Admonition from '@theme/Admonition';
import ResultsGrid from '@site/src/components/ResultsGrid';
import MetricBar from '@site/src/components/MetricBar';
import ScatterPlot from '@site/src/components/charts/ScatterPlot';
import {getRelease, releaseVersions, LATEST} from '@site/src/data';
import {pct, usd} from '@site/src/components/charts/format';
import styles from './results.module.css';

export default function Results() {
  const [version, setVersion] = useState(LATEST);
  const release = getRelease(version);

  return (
    <Layout
      title="Results"
      description="LLMSearchBench results: accuracy, citation fidelity, latency and cost."
    >
      <main className="container margin-vert--lg">
        <div className={styles.head}>
          <div>
            <h1 className={styles.title}>Results</h1>
            <p className={styles.lede}>
              {release.taskCount} tasks · {release.rows.length} models · run {release.date}
            </p>
          </div>
          <label className={styles.picker}>
            <span>Benchmark release</span>
            <select value={version} onChange={(e) => setVersion(e.target.value)}>
              {releaseVersions.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </div>

        {release.placeholder && (
          <Admonition type="warning" title="Placeholder data">
            <p>
              These numbers are scaffold values, not measurements. Replace{' '}
              <code>docs/src/data/releases/{release.version}.json</code> with real run
              output before publishing. {release.notes}
            </p>
          </Admonition>
        )}

        <ResultsGrid release={version} />

        <ScatterPlot
          title="Cost against accuracy"
          subtitle={`${release.version} · each point is one model`}
          data={release.rows.map((row) => ({
            label: row.model,
            x: row.costPer1k,
            y: row.accuracy,
            group: row.provider,
          }))}
          xLabel="USD per 1 000 tasks"
          yLabel="Accuracy"
          xFormat={usd}
          yFormat={(v) => pct(v, 0)}
          logX
          footnote="Log-scaled cost axis. Up and to the left is better."
        />

        <MetricBar metric="accuracy" title="Accuracy" release={version} colorByProvider />
        <MetricBar metric="citationF1" title="Citation F1" release={version} colorByProvider />
        <MetricBar
          metric="hallucinationRate"
          title="Unsupported-claim rate"
          release={version}
          colorByProvider
        />
        <MetricBar metric="latencyP50" title="Median latency" release={version} colorByProvider />
      </main>
    </Layout>
  );
}
