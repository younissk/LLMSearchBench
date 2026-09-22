"""Reading and writing the run artefacts.

A release directory holds three files, and nothing on the site depends on
anything outside them:

    results/<version>/
        raw.jsonl       one line per (model, task)
        summary.json    the aggregate the site renders
        manifest.json   model ids, judge id, harness commit, run date

Parsing goes through the Pydantic models in `llmsearchbench.types`, so a
malformed artefact fails at load with the offending field named.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from llmsearchbench.storage.jsonl import append_line, read_jsonl, write_jsonl
from llmsearchbench.types import Manifest, RunRecord, Summary, Task
from llmsearchbench.types.tooluse import ToolUseAttempt

RAW_FILENAME = "raw.jsonl"
SUMMARY_FILENAME = "summary.json"
MANIFEST_FILENAME = "manifest.json"

#: Indent used for every JSON file we commit. Readable diffs beat compact ones.
INDENT = 2


def load_records(path: Path) -> list[RunRecord]:
    """Load `raw.jsonl`."""
    return [RunRecord.model_validate(raw) for raw in read_jsonl(path)]


def append_record(path: Path, record: RunRecord) -> None:
    """Append one result, so an interrupted run keeps everything it already has."""
    append_line(path, record.model_dump_json())


def load_tasks(path: Path) -> list[Task]:
    """Load a task set from JSONL."""
    return [Task.model_validate(raw) for raw in read_jsonl(path)]


def save_tasks(path: Path, tasks: Iterable[Task]) -> None:
    write_jsonl(path, [task.model_dump(mode="json") for task in tasks])


def load_summary(path: Path) -> Summary:
    return Summary.model_validate_json(path.read_text(encoding="utf-8"))


def save_summary(path: Path, summary: Summary) -> None:
    """Write `summary.json` in the shape the documentation site imports.

    `exclude_none` keeps optional fields out of the file entirely rather than
    writing `null`, which the site\'s TypeScript declares as `string | undefined`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = summary.model_dump_json(indent=INDENT, exclude_none=True)
    path.write_text(text + "\n", encoding="utf-8")


def load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: Manifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=INDENT) + "\n", encoding="utf-8")


#: Fields that used to be recorded and no longer are. Attempts files are
#: expensive to produce, so a removed field must not make an old run
#: unreadable — but the models stay `extra="forbid"`, so a typo in a *current*
#: field is still caught. Removing a field means adding it here.
LEGACY_ATTEMPT_FIELDS = frozenset({"turns"})


def load_attempts(path: Path) -> list[ToolUseAttempt]:
    """Load an attempts file, tolerating fields that have since been removed."""
    attempts = []
    for raw in read_jsonl(path):
        attempts.append(
            ToolUseAttempt.model_validate(
                {k: v for k, v in raw.items() if k not in LEGACY_ATTEMPT_FIELDS}
            )
        )
    return attempts


def release_dir(root: Path, version: str) -> Path:
    return root / version


def publish_to_site(summary: Summary, site_root: Path) -> Path:
    """Copy a summary into the docs site\'s data directory.

    Registering it in `docs/src/data/index.ts` stays manual: bumping `LATEST` is
    an editorial decision, not a side effect of running the benchmark.
    """
    target = site_root / "src" / "data" / "releases" / f"{summary.version}.json"
    save_summary(target, summary)
    return target
