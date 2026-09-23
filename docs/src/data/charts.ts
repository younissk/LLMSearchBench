/**
 * Chart inputs, derived from what `llmsearchbench publish` wrote.
 *
 * Nothing here re-scores anything: the leaderboard holds the rates and the
 * item matrix holds one character per item, so every series below is a
 * reshaping of published numbers rather than a second opinion about them.
 */
import {getLeaderboard, type LeaderboardRow} from './index';
import type {ItemMeta, ModelItems, TaskItemMatrix} from './types';
import itemMatrix from './results/tool-use-correctness-items.json';
import {vendorName} from '@site/src/components/VendorIcon';

const matrices: Record<string, TaskItemMatrix> = {
  'tool-use-correctness': itemMatrix as TaskItemMatrix,
};

export function getItemMatrix(task: string): TaskItemMatrix {
  const matrix = matrices[task];
  if (!matrix) throw new Error(`No item matrix for task "${task}"`);
  return matrix;
}

/** `A` and `S` are the two right answers; `O` and `U` are the two wrong ones. */
export const DECISION_CORRECT = new Set(['A', 'S']);

export const isCorrect = (model: ModelItems, i: number) =>
  DECISION_CORRECT.has(model.decisions[i]);

// --- from the leaderboard alone ---------------------------------------------

export interface Board {
  rows: LeaderboardRow[];
  taskItems: number;
  generated: string;
}

export function board(task: string): Board {
  const data = getLeaderboard(task);
  return {rows: data.rows, taskItems: data.taskItems, generated: data.generated};
}

/** Models that can be compared on cost: an unpriced one reads zero. */
export const priced = (rows: LeaderboardRow[]) =>
  rows.filter((row) => row.costUsd > 0 && !row.isFree);

/** Vendors with their models' values, for a spread plot. */
export function byVendor(
  rows: LeaderboardRow[],
  value: (row: LeaderboardRow) => number,
): {label: string; values: number[]; names: string[]}[] {
  const groups = new Map<string, {values: number[]; names: string[]}>();
  for (const row of rows) {
    const key = vendorName(row.model);
    const group = groups.get(key) ?? {values: [], names: []};
    group.values.push(value(row));
    group.names.push(row.label);
    groups.set(key, group);
  }
  return [...groups.entries()].map(([label, group]) => ({label, ...group}));
}

// --- from the item matrix ---------------------------------------------------

export interface OutcomeMix {
  label: string;
  values: Record<string, number>;
}

/**
 * Every item of a run, sorted into what happened to it.
 *
 * A correct search is split by whether the call was well formed, because a
 * model that decides right and then calls wrong has a different problem from
 * one that decides wrong.
 */
export function outcomeMix(matrix: TaskItemMatrix): OutcomeMix[] {
  return matrix.models.map((model) => {
    const values: Record<string, number> = {
      abstained: 0,
      searchedClean: 0,
      searchedMalformed: 0,
      overSearch: 0,
      underSearch: 0,
    };
    for (let i = 0; i < model.decisions.length; i += 1) {
      const decision = model.decisions[i];
      if (decision === 'A') values.abstained += 1;
      else if (decision === 'O') values.overSearch += 1;
      else if (decision === 'U') values.underSearch += 1;
      else if (model.calls[i] === 'x') values.searchedMalformed += 1;
      else values.searchedClean += 1;
    }
    return {label: model.label, values};
  });
}

/**
 * How many models got each item right, bucketed.
 *
 * An item every model fails is usually a label this benchmark got wrong, so
 * this doubles as dataset QA rather than only a difficulty picture.
 */
export function difficultyBins(matrix: TaskItemMatrix, binCount = 10) {
  const models = matrix.models.length || 1;
  const bins = Array.from({length: binCount}, (_, i) => ({
    label: `${Math.round((i / binCount) * 100)}–${Math.round(((i + 1) / binCount) * 100)}%`,
    count: 0,
    detail: '' as string,
  }));

  matrix.items.forEach((item, i) => {
    const right = matrix.models.filter((model) => isCorrect(model, i)).length;
    const share = right / models;
    const index = Math.min(binCount - 1, Math.floor(share * binCount));
    bins[index].count += 1;
    if (!bins[index].detail) bins[index].detail = item.id;
  });

  return bins;
}

/** Items no model, or almost no model, got right — the QA worklist. */
export function hardestItems(matrix: TaskItemMatrix, limit = 12) {
  const models = matrix.models.length || 1;
  return matrix.items
    .map((item, i) => ({
      item,
      share: matrix.models.filter((model) => isCorrect(model, i)).length / models,
    }))
    .sort((a, b) => a.share - b.share)
    .slice(0, limit);
}

const label = (item: ItemMeta) => `${item.bucket}/${item.subcategory}`;

/** Per-model accuracy inside each bucket-and-subcategory. */
export function subcategoryCells(matrix: TaskItemMatrix, minItems = 8) {
  const columns = [...new Set(matrix.items.map(label))].sort();
  const counted = columns.filter(
    (column) => matrix.items.filter((item) => label(item) === column).length >= minItems,
  );

  const cells = matrix.models.flatMap((model) =>
    counted.map((column) => {
      const indices = matrix.items
        .map((item, i) => (label(item) === column ? i : -1))
        .filter((i) => i >= 0);
      const right = indices.filter((i) => isCorrect(model, i)).length;
      return {
        row: model.label,
        column,
        value: indices.length ? right / indices.length : null,
        detail: `${right}/${indices.length}`,
      };
    }),
  );

  return {
    rows: matrix.models.map((model) => model.label),
    columns: counted,
    cells,
  };
}

/**
 * How often two models agree item by item, right or wrong together.
 *
 * Two models that agree on 95% of items are one model for fine-tuning
 * purposes: the second buys almost nothing the first does not already do.
 */
export function agreementCells(matrix: TaskItemMatrix) {
  const labels = matrix.models.map((model) => model.label);
  const correctness = matrix.models.map((model) =>
    matrix.items.map((_, i) => isCorrect(model, i)),
  );

  const cells = matrix.models.flatMap((_, a) =>
    matrix.models.map((__, b) => {
      const same = correctness[a].filter((value, i) => value === correctness[b][i]).length;
      return {
        row: labels[a],
        column: labels[b],
        value: same / (matrix.items.length || 1),
        detail: `${same}/${matrix.items.length}`,
      };
    }),
  );

  return {rows: labels, columns: labels, cells};
}

/** Search rate per bucket, against the rate a perfect model would show. */
export function searchRates(rows: LeaderboardRow[]) {
  return rows.map((row) => ({
    label: row.label,
    values: {
      memory: row.overSearchMemory,
      search: row.searchAccuracy,
      noTool: row.overSearchNoTool,
    },
  }));
}
