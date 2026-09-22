---
id: reproduce
title: Reproduce a run
sidebar_position: 5
---

# Reproduce a run

```bash
git clone https://github.com/younissk/LLMSearchBench
cd LLMSearchBench
cp .env.example .env   # add the provider keys you want to evaluate
```

Then run one release against one model:

```bash
uv run llmsearchbench run \
  --release v0.1.0 \
  --model claude-opus-5 \
  --out results/local
```

Compare against the published numbers:

```bash
uv run llmsearchbench diff \
  results/local/summary.json \
  results/v0.1.0/summary.json
```

A reproduction is considered to match when every metric lands within the
release's stated tolerance (±2 accuracy points at 120 tasks). Larger gaps are
worth an issue — include your `manifest.json`.

## What you need

| Requirement | Why |
| --- | --- |
| Provider API keys | one per model you evaluate |
| Search backend key | the same backend for every model, or the run is not comparable |
| ~40 min, one machine | 120 tasks × 1 model, no parallelism |

## Cost of a reproduction

Running the full model set for one release costs roughly what the `costPer1k`
column implies, scaled to the task count — about $13 for all eight models at
120 tasks, plus judge tokens.

:::tip Run a subset first
`--tasks 20` runs a stratified fifth of the set. It is not a valid result, but
it catches a broken key or a bad harness config in three minutes instead of
forty.
:::
