import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import Leaderboard from '@site/src/components/Leaderboard';
import {leaderboards, taskIds} from '@site/src/data';
import styles from './results.module.css';

export default function Results() {
  return (
    <Layout
      title="Results"
      description="Leaderboards for every LLMSearchBench task."
    >
      <main className="container margin-vert--lg">
        <div className={styles.head}>
          <div>
            <h1 className={styles.title}>Results</h1>
            <p className={styles.lede}>
              One leaderboard per task. Every number comes from a run you can
              reproduce.
            </p>
          </div>
        </div>

        {taskIds.map((task) => {
          const board = leaderboards[task];
          return (
            <section key={task} className={styles.task}>
              <h2 className={styles.taskTitle}>
                <Link to={`/docs/tasks/${task}/`}>{board.title}</Link>
              </h2>
              <p className={styles.taskLede}>
                {board.rows.length} model{board.rows.length === 1 ? '' : 's'} ·{' '}
                {board.taskItems} items · last generated {board.generated}
              </p>
              <Leaderboard task={task} />
            </section>
          );
        })}
      </main>
    </Layout>
  );
}
