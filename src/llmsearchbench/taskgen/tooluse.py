"""Building the tool-use-correctness task set.

Two of the three buckets are derived from RetrievalQA, whose
`param_knowledge_answerable` flag is a ready-made memory check: `1` means the
authors found an LLM could answer without retrieval, `0` means it could not.
That flag is the expensive part of task admission, and reusing it is the reason
this dataset was picked first.

The third bucket is not a lookup at all and has no upstream source, so it is
generated and committed under `tasks/generated/`.

Everything here is deterministic given a seed: the same source file and the same
seed produce the same task set, byte for byte.
"""

from __future__ import annotations

import collections
import random
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import Field

from llmsearchbench.paths import DATA_RAW, TASKS
from llmsearchbench.storage import read_jsonl, write_jsonl
from llmsearchbench.taskgen.filters import (
    MEMORY_RULES,
    SEARCH_RULES,
    SourceRecord,
    first_failure,
)
from llmsearchbench.types import BenchModel
from llmsearchbench.types.tooluse import Bucket, ToolUseTask

RETRIEVALQA = DATA_RAW / "retrievalqa" / "retrievalqa.jsonl"
GENERATED_DIR = TASKS / "generated"

#: Held fixed so a rebuild reproduces the shipped set.
DEFAULT_SEED = 20260922

#: Target sizes. Deliberately small: the point of the benchmark is that a full
#: run is cheap enough to re-execute rather than trust.
DEFAULT_MEMORY = 120
DEFAULT_SEARCH = 120


class BuildReport(BenchModel):
    """Where every candidate went, so the published counts can be checked."""

    seed: int
    source_records: int
    #: bucket -> rule name -> how many candidates that rule rejected.
    dropped: dict[str, dict[str, int]] = Field(default_factory=dict)
    #: bucket -> how many survived every rule, before sampling.
    eligible: dict[str, int] = Field(default_factory=dict)
    #: bucket -> how many were sampled into the final set.
    selected: dict[str, int] = Field(default_factory=dict)
    #: bucket -> source dataset or generator -> count in the final set.
    composition: dict[str, dict[str, int]] = Field(default_factory=dict)
    adversarial: int = 0

    @property
    def total(self) -> int:
        return sum(self.selected.values())


def _load_source() -> list[SourceRecord]:
    if not RETRIEVALQA.exists():
        raise FileNotFoundError(
            f"{RETRIEVALQA} is not there. Run `make data` to fetch the source datasets."
        )
    return list(read_jsonl(RETRIEVALQA))


def _drop_ambiguous_duplicates(
    records: Sequence[SourceRecord],
) -> tuple[list[SourceRecord], int]:
    """Remove every record whose question string is not unique.

    43 question strings appear more than once, and seven of those carry
    contradictory gold answers — `Who was the director of Pilot?` has three
    different directors. The surface question has lost the entity it was
    generated from, so none of the copies is answerable as written.
    """
    counts = collections.Counter(record["question"] for record in records)
    kept = [record for record in records if counts[record["question"]] == 1]
    return kept, len(records) - len(kept)


def _to_task(record: SourceRecord, bucket: Bucket) -> ToolUseTask:
    return ToolUseTask(
        id=f"tuc-{'mem' if bucket is Bucket.MEMORY else 'sea'}-{record['question_id']}",
        bucket=bucket,
        prompt=record["question"],
        gold_answer=list(record["ground_truth"]),
        source="retrievalqa",
        source_id=record["question_id"],
        subcategory=record["data_source"],
        rationale=(
            "RetrievalQA marks this answerable from parametric memory"
            if bucket is Bucket.MEMORY
            else "RetrievalQA marks this as beyond parametric memory"
        ),
    )


def _stratified_sample(
    candidates: Sequence[SourceRecord], size: int, rng: random.Random
) -> list[SourceRecord]:
    """Sample proportionally across source datasets, so one source cannot dominate.

    PopQA is 55% of RetrievalQA by volume. Sampling uniformly would make this
    task largely a PopQA benchmark, and PopQA is a single question template.
    """
    by_source: dict[str, list[SourceRecord]] = collections.defaultdict(list)
    for record in candidates:
        by_source[record["data_source"]].append(record)

    for records in by_source.values():
        rng.shuffle(records)

    picked: list[SourceRecord] = []
    sources = sorted(by_source)
    # Round-robin rather than proportional: it lifts the small, cleaner sources
    # (realtimeqa, freshqa) toward parity instead of preserving PopQA's share.
    while len(picked) < size and any(by_source[s] for s in sources):
        for source in sources:
            if len(picked) >= size:
                break
            if by_source[source]:
                picked.append(by_source[source].pop())
    return picked


def _load_generated() -> list[ToolUseTask]:
    """The no-tool bucket, written to `tasks/generated/` rather than derived."""
    tasks: list[ToolUseTask] = []
    for path in sorted(GENERATED_DIR.glob("*.jsonl")):
        if path.name == "REJECTED.jsonl":
            continue
        for raw in read_jsonl(path):
            tasks.append(
                ToolUseTask(
                    id=f"tuc-{raw['id']}",
                    bucket=Bucket.NO_TOOL,
                    prompt=raw["prompt"],
                    source="generated",
                    source_id=raw["id"],
                    subcategory=raw["subcategory"],
                    adversarial=bool(raw.get("adversarial", False)),
                    rationale=raw.get("rationale", ""),
                )
            )
    return tasks


def build(
    *,
    seed: int = DEFAULT_SEED,
    memory_size: int = DEFAULT_MEMORY,
    search_size: int = DEFAULT_SEARCH,
) -> tuple[list[ToolUseTask], BuildReport]:
    """Assemble the task set and a report of how it was reached.

    The report is built up in plain dicts and constructed once at the end:
    `BuildReport` is frozen, like every model in this project.
    """
    rng = random.Random(seed)
    records = _load_source()
    unique, _ = _drop_ambiguous_duplicates(records)

    tasks: list[ToolUseTask] = []
    dropped: dict[str, dict[str, int]] = {}
    eligible: dict[str, int] = {}
    selected: dict[str, int] = {}
    composition: dict[str, dict[str, int]] = {}

    for bucket, flag, rules, size in (
        (Bucket.MEMORY, 1, MEMORY_RULES, memory_size),
        (Bucket.SEARCH, 0, SEARCH_RULES, search_size),
    ):
        pool = [r for r in unique if r["param_knowledge_answerable"] == flag]
        in_source = sum(1 for r in records if r["param_knowledge_answerable"] == flag)
        counts: collections.Counter[str] = collections.Counter()
        counts["duplicate-question"] = in_source - len(pool)

        candidates: list[SourceRecord] = []
        for record in pool:
            reason = first_failure(record, rules)
            if reason is None:
                candidates.append(record)
            else:
                counts[reason] += 1

        chosen = _stratified_sample(candidates, size, rng)
        bucket_tasks = sorted(
            (_to_task(record, bucket) for record in chosen), key=lambda task: task.id
        )
        tasks.extend(bucket_tasks)

        dropped[bucket.value] = dict(sorted(counts.items()))
        eligible[bucket.value] = len(candidates)
        selected[bucket.value] = len(bucket_tasks)
        composition[bucket.value] = dict(
            sorted(collections.Counter(t.subcategory for t in bucket_tasks).items())
        )

    generated = sorted(_load_generated(), key=lambda task: task.id)
    tasks.extend(generated)
    dropped[Bucket.NO_TOOL.value] = {}
    eligible[Bucket.NO_TOOL.value] = len(generated)
    selected[Bucket.NO_TOOL.value] = len(generated)
    composition[Bucket.NO_TOOL.value] = dict(
        sorted(collections.Counter(t.subcategory for t in generated).items())
    )

    report = BuildReport(
        seed=seed,
        source_records=len(records),
        dropped=dropped,
        eligible=eligible,
        selected=selected,
        composition=composition,
        adversarial=sum(1 for task in tasks if task.adversarial),
    )
    return tasks, report


def save(tasks: Iterable[ToolUseTask], path: Path) -> Path:
    write_jsonl(path, [task.model_dump(mode="json") for task in tasks])
    return path
