# Working in this repository

A benchmark is a claim about other people's software. The value of everything
here rests on the numbers being reproducible and the sources being credited, so
most of the conventions below exist to protect one of those two things.

## Layout

Two halves. The Python harness produces numbers; the Docusaurus site publishes
them. They meet at exactly one file shape — `summary.json`.

```text
src/llmsearchbench/
  types/        the records, as Pydantic models
  providers/    who serves which model, and at what price
  datasets/     source data: spec, registry, download, attribution
  scoring/      metrics, aggregation, reproduction diffing
  harness/      the run loop and the seams a model plugs into
  storage/      artefacts on disk
  ui/           the Rich consoles
  cli/          the Typer app, one module per command group
tests/          mirrors the layout above
data/           source datasets — fetched, never committed
tasks/          benchmark task sets, one JSONL per release
results/        published run artefacts
attribution/    licences and citations for every source
docs/           the documentation site
```

`src/llmsearchbench/` must stay a package directory. Flattening it would make
every module a top-level import name, and `types` would shadow stdlib `types` —
which breaks `contextlib`, and therefore `pathlib`, at interpreter start.

## Commands

```bash
make install     # uv sync + npm install
make check       # lint, types, tests, and the site's typecheck — the CI gate
make test        # pytest alone
make format      # ruff format + ruff check --fix
make data        # download source datasets (~38 MB), skipping what verifies
make docs        # docs dev server with hot reload
make help        # everything else
```

Run `make check` before calling any change done. It is what CI runs.

Run Python from the repository root, not from inside `src/llmsearchbench/` —
from in there, `types/` shadows the stdlib module of the same name.

## Invariants

These are the things that quietly destroy a benchmark. Each one has a test.

**Numbers are fractions, not percentages.** `accuracy`, `citationF1`, and
`hallucinationRate` are `0..1`. The Pydantic types reject anything outside that
range, because 87.1 renders as 8710% on the site.

**Source data is pinned to a commit and a SHA-256.** `main` is not a pin. A
checksum mismatch is a decision to make, not a warning to skip — `make data`
fails rather than accepting the new bytes.

**`data/raw/` is read-only and never committed.** Fixing a bad record means
writing a derivation into `data/processed/`, not editing the source. Otherwise
nobody can tell whether a number came from the published dataset or from our
patch of it.

**Credit is generated, not maintained.** `attribution/SOURCES.md`,
`attribution/citations.bib`, and `docs/content/data-sources.md` are rendered
from the registry in `src/llmsearchbench/datasets/registry.py`. Edit the
registry and run `make attribution`; never edit the outputs. Save the licence
text under `attribution/licenses/` whenever you add a dataset.

**Failing loudly beats substituting quietly.** An unknown model id, an
unconfigured adapter, and a missing search backend all raise with a pointer to
the file to edit. A benchmark that silently runs a different model than it
reports produces numbers nobody can place.

**The judge is part of a release's identity.** Changing the judge model is a
MAJOR version bump even if the task set is untouched.

## Two schemas, one shape

`summary.json` is written by Python and read by TypeScript, and they disagree on
naming. Run artefacts (`raw.jsonl`, `manifest.json`) are snake_case; the files
the site reads are camelCase.

Rather than spell camelCase in Python, the site-facing models in
`types/results.py` keep snake_case attributes and carry an alias. Pydantic
serialises by alias, so the JSON is unchanged.

`tests/types/test_site_contract.py` compares those aliases against
`docs/src/data/types.ts` and fails if the two drift. If you add a field to
`ResultRow`, add it to the TypeScript too — and note that `to_camel` turns
`cost_per_1k` into `costPer1K`, which is *not* what the site reads, so that one
field carries an explicit alias.

## Versioning

Two things version independently, and conflating them produces numbers nobody
can place:

- **the benchmark** — tasks, judge, harness, and the numbers they produce —
  versioned by a release tag, frozen in `results/<version>/` and
  `docs/src/data/releases/`;
- **the documentation prose** — versioned by Docusaurus, frozen with
  `make docs-version VERSION=v0.1.0`.

You do both at the same moment, but they are separate commands. The policy is
written out in `docs/content/versioning.md`.

## Conventions

**Tests state the behaviour, not the implementation.** A test name should say
what breaks if it fails. Fakes over mocks: the run loop is driven by real
implementations of its protocols (`harness/fakes.py`), so no test needs a
network or an API key.

**Rich and Typer stay in `ui/` and `cli/`.** Everything below them is
terminal-free, so the library can be driven from a notebook or another program.
The downloader takes an `on_bytes` hook rather than knowing about a progress bar.

**Exit codes are a contract**, because CI gates on them: `0` success, `1` a real
failure, `2` bad input, `3` not wired up yet.

**Committed JSON is machine-written.** `save_summary` is the only thing that
writes a release file; hand-aligning one makes `make publish` reformat it.

## Commit messages

Conventional Commits, with the package as the scope where one applies:

```text
feat(scoring): add citation F1 over gold source sets
fix(datasets): reject a checksum mismatch instead of warning
test(harness): cover an interrupted run keeping earlier records
docs: explain why raw data is never committed
chore(deps): add pydantic, rich, and typer
```

Explain *why* in the body when the diff does not make it obvious. Do not
mention the tooling used to write the change.

## State of play

The harness is wired end to end except for the provider adapters: everything
that does not need a network is implemented and tested. `llmsearchbench run`
fails with a pointer to `harness/adapters.py`, deliberately.

Known open decisions, before a first task set can be built:

- RetrievalQA passages carry `title` and `text` but **no URLs**, while
  `gold_sources` is a URL set and citation F1 scores against it. Citation
  scoring needs either a passage-to-URL mapping or a per-source variant.
- RetrievalQA `context` is not one shape: `toolqa` entries are bare strings,
  one `realtimeqa` entry is an empty object, and `score`/`id` are absent from
  some passages. Any converter must handle all five variants.
- Model prices in `providers/registry.py` are all `0.0`. Publishing a cost of
  zero would be a lie; `models_without_prices()` exists so a release can refuse.
- The results currently on the site are placeholder data
  (`"placeholder": true`), and the site renders a warning banner saying so.
