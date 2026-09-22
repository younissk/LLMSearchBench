# tasks

Benchmark task sets, one JSONL per release, committed.

```text
tasks/
  v0.1.0.jsonl      the frozen task set for release v0.1.0
  candidates/       questions drawn from source data, not yet admitted
```

One line per task:

```json
{"id": "t-001", "question": "...", "gold_answer": "...", "gold_sources": ["https://..."], "category": "multi-hop", "freshness_cutoff": "2026-01-01"}
```

A candidate becomes a task only after clearing all three admission rules —
not answerable from memory, answerable with the tool, and stable across a week.
The rules and the categories are described under
[Methodology → Task design](../docs/content/methodology/tasks.md).

Task sets are built from the datasets in [`../data/`](../data/README.md). Run
`make data` first.
