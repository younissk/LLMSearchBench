/** One model's result on one benchmark release. */
export interface ResultRow {
  /** Display name, e.g. "Claude Opus 5". */
  model: string;
  provider: string;
  /** Fraction of tasks answered correctly, 0–1. */
  accuracy: number;
  /** F1 of cited sources against the gold source set, 0–1. */
  citationF1: number;
  /** Fraction of answers containing an unsupported claim, 0–1. Lower is better. */
  hallucinationRate: number;
  /** Median wall-clock seconds per task. Lower is better. */
  latencyP50: number;
  /** USD per 1 000 tasks. Lower is better. */
  costPer1k: number;
  /** Mean search tool calls per task. */
  searchCalls: number;
}

export interface Release {
  version: string;
  /** ISO date the run was executed. */
  date: string;
  taskCount: number;
  /** Set false once these are real measured numbers. */
  placeholder: boolean;
  notes?: string;
  rows: ResultRow[];
}
