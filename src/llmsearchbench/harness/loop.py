"""The run loop.

One run is a pure function of (task set, model, harness config, judge).
Anything that is not one of those four is a bug.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from llmsearchbench.harness.config import HarnessConfig
from llmsearchbench.harness.protocols import (
    Document,
    Judge,
    ModelAdapter,
    SearchBackend,
)
from llmsearchbench.storage import append_record
from llmsearchbench.types import RunRecord, Task


class RecordingBackend:
    """Wraps a backend and keeps every document it returned, for the judge."""

    def __init__(self, inner: SearchBackend) -> None:
        self._inner = inner
        self.retrieved: list[Document] = []

    def search(self, query: str, top_k: int) -> Sequence[Document]:
        documents = self._inner.search(query, top_k)
        self.retrieved.extend(documents)
        return documents


def run_task(
    task: Task,
    model_name: str,
    adapter: ModelAdapter,
    backend: SearchBackend,
    judge: Judge,
    config: HarnessConfig,
) -> RunRecord:
    """Answer one task and judge the answer."""
    recorder = RecordingBackend(backend)
    answer = adapter.answer(task, recorder, config)
    judgement = judge.judge(task, answer, recorder.retrieved)

    return RunRecord(
        task_id=task.id,
        model=model_name,
        answer=answer.answer,
        citations=list(answer.citations),
        verdict=judgement.verdict,
        tokens_in=answer.tokens_in,
        tokens_out=answer.tokens_out,
        latency_s=answer.latency_s,
        search_calls=answer.search_calls,
        unsupported_claims=judgement.unsupported_claims,
        total_claims=judgement.total_claims,
    )


def run_tasks(
    tasks: Sequence[Task],
    model_name: str,
    adapter: ModelAdapter,
    backend: SearchBackend,
    judge: Judge,
    config: HarnessConfig,
    raw_path: Path | None = None,
) -> list[RunRecord]:
    """Run a whole task set, appending each result as it lands.

    Appending per task rather than at the end means an interrupted run keeps
    everything it already paid for.
    """
    records: list[RunRecord] = []
    for task in tasks:
        record = run_task(task, model_name, adapter, backend, judge, config)
        if raw_path is not None:
            append_record(raw_path, record)
        records.append(record)
    return records
