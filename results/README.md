# results

Run artefacts, one directory per benchmark release.

```text
results/
  <version>/
    raw.jsonl       one line per (model, task): answer, citations, tokens
    summary.json    the aggregate the documentation site renders
    manifest.json   model ids, judge id, harness commit, run date
  local/            your own runs — not committed
```

Published releases are committed: they are small, and they are the evidence
behind every number on the site. `results/local/` is ignored, so a reproduction
never collides with a published release.

```bash
make validate SUMMARY=results/v0.1.0/summary.json
make diff ACTUAL=results/local/summary.json REFERENCE=results/v0.1.0/summary.json
make publish SUMMARY=results/v0.1.0/summary.json
```

`manifest.json` is what makes a published number checkable — it pins the exact
model ids, the judge, and the harness commit that produced the run. A result
directory without one is not publishable.
