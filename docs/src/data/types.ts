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
  /** `prompted` marks a provider whose server has tool calling disabled: the
   *  tool was described in the prompt instead, so the number is not strictly
   *  comparable with a native tool-calling run. */
  toolProtocol: 'native' | 'prompted';

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

  /** Billions of parameters, measured from the published weights. Absent for a
   *  closed model, and never estimated. */
  paramsB?: number;

  /** USD for the whole run. */
  costUsd: number;
  /** The part of `costUsd` spent searching when it should not have. */
  wastedUsd: number;
  /** Spend per right decision. Zero for an unpriced model. */
  usdPerCorrectDecision: number;
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

/** One task item, as the per-item charts need it. Mirrors `ItemMeta`. */
export interface ItemMeta {
  id: string;
  bucket: 'memory' | 'search' | 'no_tool';
  subcategory: string;
  source: string;
  adversarial: boolean;
}

/** One model's per-item result, one character per item.
 *
 *  `decisions`: A correct abstain, S correct search, O over-search,
 *  U under-search. `calls`: . no call, + well-formed, x malformed. */
export interface ModelItems {
  model: string;
  label: string;
  toolProtocol: 'native' | 'prompted';
  decisions: string;
  calls: string;
}

/** Every complete run's answer on every item. */
export interface TaskItemMatrix {
  task: string;
  generated: string;
  items: ItemMeta[];
  models: ModelItems[];
}
