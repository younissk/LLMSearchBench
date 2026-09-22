# LLMSearchBench

A small, reproducible benchmark for how language models use search: retrieval
quality, citation fidelity, and what a grounded answer costs.

Documentation site: <https://younissk.github.io/LLMSearchBench/>

## Repository layout

```text
src/llmsearchbench/
  types/        the records, as Pydantic models
    base.py     shared config: frozen, extra="forbid", camelCase aliases
    enums.py    Category, Verdict
    tasks.py    Task
    runs.py     RunRecord
    results.py  ResultRow, Summary — what the site reads
    manifest.py Manifest
  providers/    who serves which model, and at what price
    entities.py what a provider and a model are
    registry.py the catalogue, and the lookups over it
  datasets/     source data
    spec.py     what a dataset is, and what it takes to credit it
    registry.py the datasets themselves, pinned by commit and checksum
    download.py fetching and verifying
    attribution.py  the generated licence and citation files
  scoring/      how a run becomes a number
    metrics.py  the per-answer formulas
    aggregate.py  records collapsed into one published row
    compare.py  a reproduction checked against a release
  harness/      running a model against a task set
    config.py   the knobs held fixed across a release
    protocols.py  the seams a model, backend, and judge plug into
    loop.py     the run loop
    adapters.py wiring an id to an implementation
    fakes.py    implementations that need no network
  storage/      artefacts on disk
    jsonl.py    the line-oriented plumbing
    artefacts.py  the typed layer over it
  ui/           the Rich consoles — the only package that knows a terminal exists
  cli/          the Typer app, one module per command group
  paths.py      where everything lives on disk
tests/          mirrors the layout above
data/           source datasets — fetched, not committed
tasks/          benchmark task sets, one JSONL per release
results/        published run artefacts
attribution/    licences and citations for every source
docs/           the documentation site (Docusaurus)
```

`src/llmsearchbench/` has to be its own directory: without it every module
would become a top-level import name, and `types` would shadow stdlib `types`.
Separation comes from the subpackages above, not from flattening.

Each top-level folder has a README explaining what belongs in it:
[`data/`](data/README.md), [`tasks/`](tasks/README.md),
[`results/`](results/README.md), [`attribution/`](attribution/README.md).

## Getting started

```bash
make install     # uv sync + npm install
make data        # download the source datasets (~38 MB)
make check       # lint, types, tests, and the site's typecheck
make help        # every target
```

`make` targets, grouped:

| Area | Targets |
| --- | --- |
| Python | `sync` `test` `test-cov` `lint` `format` `typecheck` |
| Data | `data` `data-one` `data-verify` `data-list` `data-clean` |
| Attribution | `attribution` `attribution-check` |
| Benchmark | `models` `validate` `diff` `publish` |
| Docs site | `docs` `docs-build` `docs-serve` `docs-typecheck` `docs-version` |
| Housekeeping | `clean` `clean-all` |

## Running the benchmark

```bash
cp .env.example .env    # one model key, one search key
make data               # source datasets, checksum-verified
make tasks              # build the task set

uv run llmsearchbench run --model claude-opus-5 --backend tavily --limit 20
uv run llmsearchbench score --model claude-opus-5
```

`run` prints a cost estimate and asks before spending anything, writes each
attempt as it lands, and resumes from where it stopped if interrupted. Scoring
is free and offline — rescore without paying for the run again.

Models live in `src/llmsearchbench/providers/registry.py`, each with its price;
a model with no price cannot be published. Search goes through Tavily, Brave,
or Serper — every model in a release must use the same one, and the run records
which. Full setup and costs: [Running it](docs/content/tasks/tool-use-correctness/running.mdx).

## Publishing a release

Benchmark data and documentation prose version independently — see
[the versioning policy](docs/content/versioning.md).

```bash
make publish SUMMARY=results/v0.2.0/summary.json   # copy into the site
# then register it in docs/src/data/index.ts and bump LATEST

make docs-version VERSION=v0.1.0                   # freeze the outgoing prose
# then write docs/changelog/2026-MM-DD-v0.2.0.md
```

Pushing to `main` builds and deploys the site automatically.

## Data and credit

Source datasets are declared in `src/llmsearchbench/datasets.py`, pinned to an
upstream commit and a SHA-256 per file. `make data` fetches what is missing and
skips what already verifies; a file whose checksum does not match is rejected
rather than accepted with a warning.

Attribution is generated from that same registry — `attribution/SOURCES.md`,
`attribution/citations.bib`, and the site's
[Data sources](docs/content/data-sources.md) page. A dataset therefore cannot be
added without its licence and citation appearing everywhere they should, and
`tests/test_attribution.py` fails if the committed copies drift.

Currently registered: [RetrievalQA](https://github.com/hyintell/RetrievalQA)
(MIT) — 2,785 short-form open-domain questions carrying a
`param_knowledge_answerable` flag.

## Types

Records are Pydantic models, frozen and `extra="forbid"`, so a typo'd key in an
artefact fails at load rather than silently dropping a metric. Validation lives
in the type, not in the caller: `accuracy` is a `Fraction`, so 87.1 is rejected
at the boundary instead of rendering as 8710% on the site.

Two JSON dialects meet here. Run artefacts are snake_case; the files the
documentation site reads are camelCase. Rather than spell camelCase in Python,
the site-facing models keep snake_case attributes and carry an alias, and
Pydantic serialises by alias.

`tests/test_site_contract.py` compares those aliases against
`docs/src/data/types.ts` and fails if the two drift apart. It also parses every
file in `docs/src/data/releases/` — so a release that would render as
`undefined` on the site fails in CI instead.

## Command line

Typer for the interface, Rich for the output. Both are confined to `cli.py` and
`console.py`; everything below stays terminal-free, so the library can be driven
from a notebook or another program with no console attached.

```bash
llmsearchbench --help
llmsearchbench models          # the catalogue, with prices and their dates
llmsearchbench data list       # the dataset registry
llmsearchbench data download   # fetch, with a progress bar
```

Exit codes are part of the contract, because CI gates on them: `0` success,
`1` a real failure, `2` bad input, `3` not wired up yet.

## One-time GitHub setup

In **Settings → Pages**, set **Source** to **GitHub Actions**. No `gh-pages`
branch is involved.
