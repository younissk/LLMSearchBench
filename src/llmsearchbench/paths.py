"""Where things live on disk.

One module owns the layout so nothing else has to guess at relative paths.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Downloaded source datasets. Never edited in place, never committed.
DATA_RAW = REPO_ROOT / "data" / "raw"

#: Anything derived from `DATA_RAW`. Reproducible, so also not committed.
DATA_PROCESSED = REPO_ROOT / "data" / "processed"

#: Pinned URLs and checksums for every source dataset. Committed.
DATASETS_LOCK = REPO_ROOT / "data" / "datasets.lock.json"

#: Sizes measured from the published weights, written by
#: `scripts/model_params.py` and read at publish time.
MODEL_PARAMS = REPO_ROOT / "data" / "model_params.json"

#: What each provider will enforce about a reply's shape, written by
#: `scripts/model_capabilities.py`. A provider fact, so it carries a date.
MODEL_CAPABILITIES = REPO_ROOT / "data" / "model_capabilities.json"

#: Benchmark task sets, one JSONL per release. Committed.
TASKS = REPO_ROOT / "tasks"

#: Run artefacts. `results/<version>/` is committed; `results/local/` is not.
RESULTS = REPO_ROOT / "results"

#: Who we got what from: licences, citations, and the generated summary.
ATTRIBUTION = REPO_ROOT / "attribution"
LICENSES = ATTRIBUTION / "licenses"

#: The documentation site.
SITE = REPO_ROOT / "docs"
SITE_DOCS = SITE / "content"
SITE_RELEASES = SITE / "src" / "data" / "releases"


def dataset_dir(name: str) -> Path:
    """Where one source dataset's raw files land."""
    return DATA_RAW / name
