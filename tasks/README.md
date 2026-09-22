# tasks

Benchmark task sets, one JSONL per release, committed.

```text
tasks/
  tool-use-correctness.jsonl         the built task set, committed
  tool-use-correctness.report.json   where every candidate went
  generated/                         prompts written for this benchmark
  generated/REJECTED.jsonl           generated items cut on review, with reasons
```

## tool-use correctness

The first task. Each line is one prompt plus what the model is expected to do
about the search tool:

```json
{"id": "tuc-sea-realtimeqa_20231013_3", "bucket": "search", "prompt": "...", "gold_answer": ["£5,000"], "source": "retrievalqa", "source_id": "realtimeqa_20231013_3", "subcategory": "realtimeqa", "adversarial": false, "rationale": "..."}
```

Three buckets: `memory` (the model should already know it), `search` (it cannot
know it), and `no_tool` (there is nothing to look up). Only `search` expects a
tool call.

```bash
make data          # the source datasets have to be present first
make tasks         # rebuild, deterministic given the seed
make tasks-stats   # describe what is committed
```

The build is seeded, so a rebuild reproduces the committed file exactly — a test
asserts it. `tool-use-correctness.report.json` records how many candidates each
admission rule rejected; the reasoning behind the rules is on the
[task's documentation page](../docs/content/tasks/tool-use-correctness.md).

`generated/` holds the `no_tool` prompts, which have no upstream source and were
written for this benchmark. Items cut during review stay in `REJECTED.jsonl`
with the reason, rather than being deleted.
