import React from 'react';
import styles from './ChartGallery.module.css';
import {
  BarChart,
  BoxPlotChart,
  DumbbellChart,
  GroupedBarChart,
  HeatmapChart,
  HistogramChart,
  ScatterChart,
  StackedBarChart,
} from '@site/src/components/charts';
import {
  agreementCells,
  board,
  byVendor,
  difficultyBins,
  getItemMatrix,
  hardestItems,
  outcomeMix,
  priced,
  searchRates,
  subcategoryCells,
} from '@site/src/data/charts';

const median = (values: number[]) => {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length ? sorted[Math.floor(sorted.length / 2)] : 0;
};

const money = (v: number) => `$${v.toFixed(v < 1 ? 3 : 2)}`;

function Section({
  index,
  title,
  question,
  children,
}: {
  index: number;
  title: string;
  question: string;
  children: React.ReactNode;
}) {
  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>
        <span className={styles.index}>{index}</span> {title}
      </h2>
      <p className={styles.question}>{question}</p>
      {children}
    </section>
  );
}

/**
 * Every chart on the table at once, so the set can be pruned by looking at it.
 *
 * Each one is drawn from the published files only — the leaderboard for the
 * rates and the item matrix for anything per-item.
 */
export default function ChartGallery({task}: {task: string}) {
  const {rows, taskItems} = board(task);
  const matrix = getItemMatrix(task);

  const complete = rows.filter((row) => row.complete);
  const withCost = priced(complete);

  const guideX = median(complete.map((row) => row.overSearchMemory));
  const guideY = median(complete.map((row) => row.underSearch));

  return (
    <div>
      <Section
        index={1}
        title="Over-search vs under-search"
        question="Which way is a model wrong — does it reach for the tool it does not need, or skip the one it does?"
      >
        <ScatterChart
          title="The two ways to get the decision wrong"
          subtitle={`${complete.length} models, ${taskItems} items each`}
          points={complete.map((row) => ({
            label: row.label,
            x: row.overSearchMemory,
            y: row.underSearch,
            detail: {Decision: `${(row.decisionAccuracy * 100).toFixed(1)}%`},
          }))}
          xLabel="Searched a memory item (over-search)"
          yLabel="Skipped a search item (under-search)"
          guides={{x: guideX, y: guideY}}
          quadrantLabels={[
            'trusts itself too much',
            'wrong in both directions',
            'searches on reflex',
            'well calibrated',
          ]}
          footnote="Dashed lines are the medians of each axis, not a pass mark. Bottom-left is better."
        />
      </Section>

      <Section
        index={2}
        title="Outcome mix"
        question="What happened to all 360 items of one run?"
      >
        <StackedBarChart
          title="Every item of every run, sorted into what happened"
          subtitle="Normalised to 100%; each run is the same 360 items"
          rows={outcomeMix(matrix)}
          sortBy="abstained"
          series={[
            {key: 'abstained', label: 'Right to not search', color: 'var(--series-3)'},
            {key: 'searchedClean', label: 'Right to search, clean call', color: 'var(--series-1)'},
            {
              key: 'searchedMalformed',
              label: 'Right to search, malformed call',
              color: 'var(--series-4)',
            },
            {key: 'overSearch', label: 'Searched, should not have', color: 'var(--series-2)'},
            {key: 'underSearch', label: 'Did not search, should have', color: 'var(--series-5)'},
          ]}
          footnote="Only complete runs appear here: a partial run would not be a whole bar."
        />
      </Section>

      <Section
        index={3}
        title="Cost against accuracy"
        question="What is the cheapest model at each level of accuracy?"
      >
        <ScatterChart
          title="Spend per run against decision accuracy"
          subtitle={`${withCost.length} priced models; free and unpriced endpoints left out`}
          points={withCost.map((row) => ({
            label: row.label,
            x: row.costUsd,
            y: row.decisionAccuracy,
            detail: {'Per right decision': money(row.usdPerCorrectDecision)},
          }))}
          xLabel="Cost of one 360-item run (USD)"
          yLabel="Decision accuracy"
          xFormat={money}
          footnote="Up and to the left is better. Prices are list prices at the date on the leaderboard."
        />
      </Section>

      <Section
        index={4}
        title="Trap sensitivity"
        question="How much accuracy does a model lose on items worded to bait a search?"
      >
        <DumbbellChart
          title="Overall accuracy against accuracy on the traps"
          subtitle="29 of the 360 items are worded to tempt a search that is not needed"
          rows={complete.map((row) => ({
            label: row.label,
            from: row.decisionAccuracy,
            to: row.adversarialAccuracy,
          }))}
          fromLabel="All items"
          toLabel="Trap items"
          footnote="A long line to the left is a model that reads bait as a reason to search."
        />
      </Section>

      <Section
        index={5}
        title="Search rate per bucket"
        question="How close is each model to the behaviour a perfect model would show?"
      >
        <GroupedBarChart
          title="How often each model searched, by what the item needed"
          subtitle="The dark tick on each bar is the perfect rate"
          rows={searchRates(complete)}
          sortBy="search"
          series={[
            {key: 'memory', label: 'memory items', color: 'var(--series-2)', target: 0},
            {key: 'search', label: 'search items', color: 'var(--series-1)', target: 1},
            {key: 'noTool', label: 'no_tool items', color: 'var(--series-4)', target: 0},
          ]}
        />
      </Section>

      <Section
        index={6}
        title="Latency, thinking, accuracy"
        question="Do slower, more thinking-heavy models decide better?"
      >
        <ScatterChart
          title="Mean latency against decision accuracy"
          subtitle="Dot area is the share of output tokens spent thinking"
          points={complete.map((row) => ({
            label: row.label,
            x: row.latencyMeanS,
            y: row.decisionAccuracy,
            size: row.reasoningShare,
            detail: {'Mean output tokens': row.tokensOutMean.toFixed(0)},
          }))}
          xLabel="Mean seconds per item"
          yLabel="Decision accuracy"
          xFormat="seconds"
          sizeLabel="Thinking share"
          footnote="Providers that do not report reasoning tokens show as the smallest dot, not as zero thinking."
        />
      </Section>

      <Section
        index={7}
        title="Wasted spend"
        question="How much money went on searches that should never have happened?"
      >
        <BarChart
          title="Cost of the unnecessary searches"
          subtitle="The part of a run's bill spent on memory and no_tool items the model searched anyway"
          data={withCost.map((row) => ({label: row.label, value: row.wastedUsd}))}
          format={money}
          lowerIsBetter
          footnote="Lower is better. A cheap model can still waste most of its bill."
        />
      </Section>

      <Section
        index={8}
        title="Vendor spread"
        question="Is a vendor consistently good, or does one model carry the family?"
      >
        <BoxPlotChart
          title="Decision accuracy within each vendor"
          subtitle="Every dot is one model"
          groups={byVendor(complete, (row) => row.decisionAccuracy)}
          valueLabel="Decision accuracy"
        />
      </Section>

      <Section
        index={9}
        title="Item difficulty"
        question="Are there items that every model fails — and are those items actually mislabelled?"
      >
        <HistogramChart
          title="How many models got each item right"
          subtitle={`${matrix.items.length} items across ${matrix.models.length} complete runs`}
          bins={difficultyBins(matrix)}
          xLabel="Share of models that decided this item correctly"
          yLabel="Items"
          footnote="The leftmost bar is the dataset-QA worklist: an item nobody gets right is often an item labelled wrong."
        />
        <table className={styles.table}>
          <caption>Hardest items, and how many models decided them correctly</caption>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">Bucket</th>
              <th scope="col">Subcategory</th>
              <th scope="col">Models right</th>
            </tr>
          </thead>
          <tbody>
            {hardestItems(matrix).map(({item, share}) => (
              <tr key={item.id}>
                <td>
                  <code>{item.id}</code>
                </td>
                <td>{item.bucket}</td>
                <td>{item.subcategory}</td>
                <td>{`${Math.round(share * matrix.models.length)} of ${matrix.models.length}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section
        index={10}
        title="Where the accuracy comes from"
        question="Which kinds of prompt does a model handle, and which does it not?"
      >
        {(() => {
          const {rows: heatRows, columns, cells} = subcategoryCells(matrix);
          return (
            <HeatmapChart
              title="Decision accuracy by bucket and subcategory"
              subtitle="Subcategories with fewer than eight items are left out"
              rows={heatRows}
              columns={columns}
              cells={cells}
              domain={[0, 1]}
              rowLabel="Accuracy"
              columnLabel="Subcategory"
              footnote="Darker is more accurate. A pale column is a kind of prompt the whole field struggles with."
            />
          );
        })()}
      </Section>

      <Section
        index={11}
        title="Model agreement"
        question="Which models behave alike — and which would add nothing as a second choice?"
      >
        {(() => {
          const {rows: agreeRows, columns, cells} = agreementCells(matrix);
          return (
            <HeatmapChart
              title="How often two models decide the same item the same way"
              subtitle="Right together or wrong together both count as agreement"
              rows={agreeRows}
              columns={columns}
              cells={cells}
              domain={[0.5, 1]}
              rowLabel="Agreement"
              columnLabel="Compared with"
              labelWidth={170}
              cellHeight={18}
              footnote="The diagonal is 100% by definition. A dark off-diagonal pair is two models that are hard to tell apart."
            />
          );
        })()}
      </Section>
    </div>
  );
}
