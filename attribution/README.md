# attribution

Who we got what from.

```text
attribution/
  SOURCES.md      generated: every dataset, its licence, files and citation
  citations.bib   generated: BibTeX for every source, verbatim
  licenses/       the licence text as we received it, one file per source
```

`SOURCES.md`, `citations.bib`, and the site's
[Data sources](../docs/content/data-sources.md) page are **generated** from the
registry in `src/llmsearchbench/datasets.py`:

```bash
make attribution         # regenerate all three
make attribution-check   # fail if the committed copies are stale
```

Editing them by hand is a mistake — the next `make attribution` overwrites it.
Change the registry instead. Generating rather than maintaining these means a
dataset cannot be added without its licence and citation appearing everywhere
they should.

`licenses/` is the exception: those files are copied from the source and are
never generated. Save one whenever you add a dataset.
