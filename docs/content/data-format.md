---
id: data-format
title: Data format
sidebar_position: 4
---

# Data format

The site renders one JSON file per benchmark release, and nothing else. If your
runner emits this shape, the site picks it up.

## `summary.json`

```json
{
  "version": "v0.1.0",
  "date": "2026-09-22",
  "taskCount": 120,
  "placeholder": false,
  "notes": "optional free text shown above the table",
  "rows": [
    {
      "model": "Claude Opus 5",
      "provider": "Anthropic",
      "accuracy": 0.871,
      "citationF1": 0.804,
      "hallucinationRate": 0.041,
      "latencyP50": 14.2,
      "costPer1k": 38.4,
      "searchCalls": 4.1
    }
  ]
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `accuracy` | number 0–1 | not a percentage — the site formats it |
| `citationF1` | number 0–1 | harmonic mean of set precision and recall |
| `hallucinationRate` | number 0–1 | unsupported-claim rate, lower is better |
| `latencyP50` | seconds | median, not mean |
| `costPer1k` | USD | list price, judge tokens excluded |
| `searchCalls` | number | mean per task |

The TypeScript definition is the source of truth:
[`src/data/types.ts`](https://github.com/younissk/LLMSearchBench/blob/main/docs/src/data/types.ts).

## Adding a release to the site

```bash
# 1. drop the summary in
cp results/v0.2.0/summary.json docs/src/data/releases/v0.2.0.json

# 2. register it
#    docs/src/data/index.ts
#      import v020 from './releases/v0.2.0.json';
#      releases['v0.2.0'] = v020;
#      export const LATEST = 'v0.2.0';

# 3. freeze the prose for the release you just superseded
cd docs && npm run version:cut -- v0.1.0
```

Step 3 is separate on purpose — see [versioning](./versioning.md).

## `raw.jsonl`

One line per (model, task). Not rendered on the site; published alongside each
release so anyone can recompute the aggregates.

```json
{"task_id":"t-041","model":"...","answer":"...","citations":["https://..."],"verdict":"correct","tokens_in":8123,"tokens_out":412,"latency_s":13.8,"search_calls":4}
```
