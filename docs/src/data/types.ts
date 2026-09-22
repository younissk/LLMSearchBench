/** One model's published result for one task. Mirrors
 *  `src/llmsearchbench/types/leaderboard.py`; the two are kept in step by hand. */
export interface LeaderboardRow {
  model: string;
  label: string;
  provider: string;
  /** How many items this model was scored on. */
  items: number;
  /** False when the run did not cover the whole task set. */
  complete: boolean;

  /** Share of right search-or-not decisions, 0–1. */
  decisionAccuracy: number;
  memoryAccuracy: number;
  searchAccuracy: number;
  noToolAccuracy: number;
  adversarialAccuracy: number;
  wellFormedRate: number;

  overSearchMemory: number;
  overSearchNoTool: number;
  underSearch: number;

  /** USD for the whole run. */
  costUsd: number;
  isFree: boolean;
  tokensOutMean: number;
  /** Share of output tokens spent thinking, where reported. */
  reasoningShare: number;
  latencyMeanS: number;
}

export interface TaskLeaderboard {
  task: string;
  title: string;
  /** ISO date the file was generated. */
  generated: string;
  /** Items in the full task set, so partial runs are obvious. */
  taskItems: number;
  rows: LeaderboardRow[];
}
