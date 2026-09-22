# data

Source datasets and anything derived from them. **Nothing in here is committed**
except this file and `datasets.lock.json` — the data is re-fetchable, and a
35 MB JSONL in git history is 35 MB forever.

```text
data/
  raw/<dataset>/        exactly what the source published, never edited
  processed/<dataset>/  anything we derive from raw/
  datasets.lock.json    pinned URLs and checksums (committed)
```

## Getting the data

```bash
make data          # download everything, skipping what already verifies
make data-list     # what is in the registry
make data-verify   # check what is on disk against the pinned checksums
make data-clean    # delete raw/ and processed/
```

## The rules

1. **`raw/` is read-only.** Fixing a bad record means writing a derivation step
   into `processed/`, not editing the source. Otherwise nobody can tell whether
   a number came from the published dataset or from our patch of it.
2. **Every file is pinned to a SHA-256.** `make data` refuses a file that does
   not match, and the mismatch message says so rather than carrying on. If a
   source changes upstream, that is a decision to make, not a surprise to absorb.
3. **Pin to a commit, never to a branch.** `main` moves.
4. **Credit travels with the data.** Licence texts live in
   [`../attribution/licenses/`](../attribution/licenses/); the registry that
   generates the credit is `src/llmsearchbench/datasets.py`.

Adding a dataset: add a `DatasetSpec` to that registry, save its licence text
under `attribution/licenses/`, then run `make data && make attribution`.
