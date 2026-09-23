import React, {useState} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import styles from './DiscriminationExample.module.css';

export interface Candidate {
  id: string;
  text: string;
  title?: string;
  source_id?: string;
}

export interface DiscriminationItem {
  id: string;
  category: 'web' | 'wikipedia' | 'no_answer';
  question: string;
  candidates: Candidate[];
  relevance: Record<string, number>;
  supporting_ids: string[];
  gold_answer: string[];
  noise_tier: 'easy' | 'medium' | 'hard';
  label_source: 'human' | 'derived';
  source: string;
  source_id: string;
  subcategory: string;
  variant_of?: string;
  rationale?: string;
}

const GRADE_LABEL: Record<number, string> = {
  3: 'perfect — answers it',
  2: 'highly relevant',
  1: 'related, does NOT answer it',
  0: 'not relevant',
};

const EXPECTED: Record<DiscriminationItem['category'], string> = {
  web: 'find the passages that answer the query and rank them first',
  wikipedia: 'find the two paragraphs that together carry the answer',
  no_answer: 'say that these results do not answer the question',
};

/**
 * One item, with its grades shown.
 *
 * This is the answer key, not the model's view — the point of the page is to
 * read the labels and argue with them. What a model is given is the question
 * and the candidates, in this order, with no grades.
 */
export default function DiscriminationExample({item}: {item: DiscriminationItem}) {
  const [hideGrades, setHideGrades] = useState(false);

  const relevant = item.supporting_ids.length;
  const ordered = [...item.candidates];

  return (
    <div className={styles.wrap}>
      <div className={styles.tags}>
        <span className={clsx(styles.tag, styles[item.category])}>{item.category}</span>
        <span className={styles.tag}>{item.noise_tier} · {item.candidates.length} results</span>
        <span className={styles.tag}>{item.subcategory}</span>
        <span className={clsx(styles.tag, item.label_source === 'human' && styles.human)}>
          {item.label_source} labels
        </span>
      </div>

      <blockquote className={styles.question}>{item.question}</blockquote>

      <dl className={styles.facts}>
        <dt>Right move</dt>
        <dd>{EXPECTED[item.category]}</dd>
        <dt>Relevant</dt>
        <dd>
          <strong>
            {relevant} of {item.candidates.length}
          </strong>
          {relevant > 0 && <> · candidates {item.supporting_ids.join(', ')}</>}
        </dd>
        {item.gold_answer.length > 0 && (
          <>
            <dt>Answer</dt>
            <dd>{item.gold_answer.join(' · ')}</dd>
          </>
        )}
        <dt>Source</dt>
        <dd>
          {item.source} <code>{item.source_id}</code>
        </dd>
        {item.rationale && (
          <>
            <dt>Why these grades</dt>
            <dd>{item.rationale}</dd>
          </>
        )}
      </dl>

      <div className={styles.toolbar}>
        <button
          type="button"
          className={clsx(styles.filter, hideGrades && styles.filterActive)}
          onClick={() => setHideGrades((value) => !value)}
        >
          {hideGrades ? 'Grades hidden — read it as a model does' : 'Hide the grades'}
        </button>
        {item.variant_of && (
          <span className={styles.variant}>
            same question as{' '}
            <Link to={`/docs/discrimination-examples/${item.variant_of}`}>
              {item.variant_of}
            </Link>{' '}
            at a
            different noise tier
          </span>
        )}
      </div>

      <ol className={styles.candidates}>
        {ordered.map((candidate) => {
          const grade = item.relevance[candidate.id] ?? 0;
          return (
            <li key={candidate.id} className={styles.candidate}>
              <div className={styles.candidateHead}>
                <span className={styles.candidateId}>[{candidate.id}]</span>
                {candidate.title && <span className={styles.title}>{candidate.title}</span>}
                {!hideGrades && (
                  <span className={clsx(styles.grade, styles[`g${grade}`])}>
                    {grade} · {GRADE_LABEL[grade]}
                  </span>
                )}
              </div>
              <p className={styles.text}>{candidate.text}</p>
            </li>
          );
        })}
      </ol>

      <p className={styles.footnote}>
        Candidate order is a seeded shuffle — in every source the relevant passages come
        first, so shuffling is what stops position from being the answer.{' '}
        <Link to="/docs/discrimination-examples/">All items</Link>
      </p>
    </div>
  );
}
