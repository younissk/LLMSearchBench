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
unconfigured adapter, and a missing API key all raise with a pointer to the
file to edit. A benchmark that silently runs a different model than it
reports produces numbers nobody can place.

**The judge is part of a release's identity.** Changing the judge model is a
MAJOR version bump even if the task set is untouched.

**A missing measurement is not a zero.** A failed request, a reply with no text
and no tool call, and a reply no parser could read are all recorded and left
out of the score. Counting them as answers put a model that failed all 360
items into mid-table once, and scored 478 silent replies across 17 models as
deliberate decisions. A rerun retries them; scoring never guesses at them.

**A measure that does not apply is not a zero either.** A `no_answer` item has
nothing to rank and nothing to recall. Those columns are `None` and the
averages skip them. Filling them with zeros once cost a model 28 points of
precision for getting the items right.

**Label provenance travels with the item.** `label_source` says who judged
relevance (`human` or `derived`); `answer_source` says where a gold answer came
from (`dataset`, `annotated`, `none`). Validators refuse an item that carries
an answer without saying where it came from. Never average the two kinds into
one number without saying so.

**A model-written label has to be checkable.** An annotated answer must be a
verbatim span of the passage it came from, and the script verifies that rather
than trusting it. Same rule for a judge: a verdict must quote its evidence, and
a quote that is not in the cited document is discarded.

**Only what may be redistributed is committed.** MS MARCO grants
non-commercial research use and extends no licence, so its passages are built
locally and git-ignored while a manifest of ids and checksums is committed.
Check a source's terms before adding its text to `tasks/`.

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
what breaks if it fails. Fakes over mocks: the run loop is driven through a
fake Messages API, so no test needs a network or an API key.

**Rich and Typer stay in `ui/` and `cli/`.** Everything below them is
terminal-free, so the library can be driven from a notebook or another program.
The downloader takes an `on_bytes` hook rather than knowing about a progress bar.

**The search tool is offered, never executed.** The task measures whether a
model reaches for it, and that decision happens before any result comes back.
There is no search backend and no second API to configure. Do not add one
without a reason that survives the question "what does running the search
tell us that the decision does not?"

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

Kept short on purpose. The full picture — every number, every known-broken
provider, every decision and why — is in `docs/content/status.mdx`, which
renders as **Where it stands** on the site. Update that page, not this section.

- **Task 1, tool-use correctness:** done. 360 items, 36 models, published.
- **Task 2, search-result discrimination:** built. 331 items, 199 scorable,
  one model run. Scores the answer and nothing else.
- **Task 3, search quality:** design only.
- **No judge runs yet.** The design is written up and tested; the groundedness
  column is absent rather than zero.

Provider gotchas that will waste an afternoon otherwise: Moonshot rejects any
`temperature` but 1; Avey serves tools on `/llm/responses` only and is rate
limited to roughly one item per seven minutes; two of the three free OpenRouter
endpoints return nothing at all.

## Running things

- `npm run build` is the only check that catches broken links — the dev server
  serves an SPA fallback for every path, so a broken link returns 200 there.
- The docs dev server needs `NODE_OPTIONS=--max-old-space-size=8192`.
- Never `pkill -f` on a pattern that matches the command you are running from.
  It kills the shell, and anything later in the same compound command never
  happens. This has cost two shells and one half-written script.
- Run each model as its own process. A saturated endpoint held up a working one
  for an hour when they shared a sequential loop.
