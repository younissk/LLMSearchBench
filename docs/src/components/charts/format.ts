export const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`;
export const usd = (v: number) => `$${v.toFixed(v < 10 ? 2 : 0)}`;
export const secs = (v: number) => `${v.toFixed(1)}s`;
export const num = (v: number, digits = 1) => v.toFixed(digits);

export type Formatter = (v: number) => string;

export const formatters: Record<string, Formatter> = {
  percent: (v) => pct(v),
  usd,
  seconds: secs,
  number: (v) => num(v),
};
