import React, {useMemo, useState} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import styles from './ExampleReport.module.css';
import VendorIcon from '@site/src/components/VendorIcon';

export interface ExampleModelResult {
  model: string;
  label: string;
  toolProtocol: 'native' | 'prompted';
  searched: boolean;
  correct: boolean;
  query?: string;
  callProblem?: string;
  answerExcerpt?: string;
}

export interface ExampleReportData {
  id: string;
  bucket: 'memory' | 'search' | 'no_tool';
  subcategory: string;
  source: string;
  sourceId?: string;
  adversarial: boolean;
  prompt: string;
  goldAnswer: string[];
  rationale?: string;
  expectsSearch: boolean;
  results: ExampleModelResult[];
}

const EXPECTED: Record<ExampleReportData['bucket'], string> = {
  memory: 'answer from memory — the model should already know this',
  search: 'search — this is past or beyond what a model can hold',
  no_tool: 'answer directly — there is no fact to look up',
};

type Filter = 'all' | 'right' | 'wrong';

/** One task item, and what every complete run did with it. */
export default function ExampleReport({report}: {report: ExampleReportData}) {
  const [filter, setFilter] = useState<Filter>('all');

  const right = report.results.filter((result) => result.correct).length;
  const total = report.results.length;
  const searched = report.results.filter((result) => result.searched).length;

  const shown = useMemo(() => {
    const rows =
      filter === 'all'
        ? report.results
        : report.results.filter((result) =>
            filter === 'right' ? result.correct : !result.correct,
          );
    return [...rows].sort((a, b) => Number(b.correct) - Number(a.correct));
  }, [report.results, filter]);

  return (
    <div className={styles.wrap}>
      <div className={styles.tags}>
        <span className={clsx(styles.tag, styles[report.bucket])}>{report.bucket}</span>
        <span className={styles.tag}>{report.subcategory}</span>
        <span className={styles.tag}>{report.source}</span>
        {report.adversarial && (
          <span className={clsx(styles.tag, styles.trap)}>trap wording</span>
        )}
      </div>

      <blockquote className={styles.prompt}>{report.prompt}</blockquote>

      <dl className={styles.facts}>
        <dt>Right move</dt>
        <dd>{EXPECTED[report.bucket]}</dd>
        {report.goldAnswer.length > 0 && (
          <>
            <dt>Accepted answers</dt>
            <dd>{report.goldAnswer.join(' · ')}</dd>
          </>
        )}
        {report.rationale && (
          <>
            <dt>Why this bucket</dt>
            <dd>{report.rationale}</dd>
          </>
        )}
        <dt>Models right</dt>
        <dd>
          <strong>
            {right} of {total}
          </strong>{' '}
          ({total ? ((right / total) * 100).toFixed(0) : 0}%) · {searched} searched
        </dd>
      </dl>

      {right === 0 && total > 0 && (
        <div className={styles.warning}>
          No model got this one right. That is usually worth reading as a question about
          the label, not only about the models.
        </div>
      )}

      <div className={styles.toolbar}>
        {(['all', 'right', 'wrong'] as Filter[]).map((value) => (
          <button
            key={value}
            type="button"
            className={clsx(styles.filter, filter === value && styles.filterActive)}
            onClick={() => setFilter(value)}
          >
            {value === 'all' ? `All ${total}` : value === 'right' ? `Right ${right}` : `Wrong ${total - right}`}
          </button>
        ))}
      </div>

      <div className={styles.scroll}>
        <table className={styles.table}>
          <caption className="sr-only">What each model did with item {report.id}</caption>
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col">Did it search?</th>
              <th scope="col">Verdict</th>
              <th scope="col">Query or answer</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((result) => (
              <tr key={result.model}>
                <td className={styles.model}>
                  <span className={styles.modelName}>
                    <VendorIcon model={result.model} />
                    {result.label}
                  </span>
                  {result.toolProtocol === 'prompted' && (
                    <span className={styles.protocol} title="tool described in the prompt">
                      prompted
                    </span>
                  )}
                </td>
                <td>{result.searched ? 'searched' : 'answered'}</td>
                <td>
                  <span className={result.correct ? styles.right : styles.wrong}>
                    {result.correct ? 'right' : 'wrong'}
                  </span>
                  {result.callProblem && (
                    <span className={styles.problem}> · {result.callProblem}</span>
                  )}
                </td>
                <td className={styles.text}>
                  {result.searched ? (
                    <code>{result.query || '(empty query)'}</code>
                  ) : (
                    result.answerExcerpt || <span className={styles.muted}>no text</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className={styles.footnote}>
        Only complete runs appear. Answers are cut at 320 characters — they are here to
        read, not to score; the scoring is the search-or-not decision.{' '}
        <Link to="/docs/examples/">All examples</Link>
      </p>
    </div>
  );
}
