"""Running the search-result-discrimination task.

One prompt carrying a question and its candidate set, one reply, one record.
No tool is offered and no retrieval happens: the results are already in the
prompt, identical for every model, which is the whole point of the task.

The raw reply is what gets stored. Parsing it into a ranking and a set of
cited candidates happens at scoring time, so a parser fix is a re-score rather
than a re-run — the same reason costs are derived from recorded tokens instead
of being written down.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from pydantic import Field

from llmsearchbench.harness.adapters import Turn
from llmsearchbench.storage import append_line
from llmsearchbench.types import BenchModel
from llmsearchbench.types.discrimination import DiscriminationTask

#: Parallel requests. Lower than the first task's eight: a candidate set is
#: ten times the prompt, and the free endpoints this is first run against rate
#: limit on tokens rather than on requests.
DEFAULT_CONCURRENCY = 4

INSTRUCTIONS = """\
You are given a question and a numbered list of search results. Some of the \
results answer the question. Some are about the same topic but do not answer \
it. Some are unrelated. Nothing tells you which is which.

Reply with one JSON object and nothing else:

{"ranking": ["3", "1", "4"], "relevant": ["3"], "answer": "..."}

- "ranking": every result id, most useful for answering the question first.
- "relevant": only the ids that actually answer the question. If none of them \
do, return an empty list.
- "answer": the answer supported by the results you listed as relevant. If \
none of them answer the question, say so instead of answering from your own \
knowledge.

Judge the results only on whether they answer this question. Do not use \
anything you know beyond them."""


class DiscriminationAttempt(BenchModel):
    """What one model replied to one candidate set.

    Raw observation only. The reply is kept verbatim: everything scored is
    derived from it, so a scoring change never needs the model again.
    """

    task_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reply: str = ""

    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    latency_s: float = Field(default=0.0, ge=0)
    stop_reason: str = ""
    error: str = ""

    @property
    def failed(self) -> bool:
        return bool(self.error)


#: Called after each item with (done, total, task, attempt).
ProgressHook = Callable[[int, int, DiscriminationTask, DiscriminationAttempt], None]


class CompletionAdapter(Protocol):
    """What the run loop needs from a provider adapter."""

    def complete(self, prompt: str, temperature: float = 0.0) -> Turn: ...


def build_prompt(task: DiscriminationTask) -> str:
    """The question, then the results, in the order the task set fixed them."""
    results = "\n\n".join(f"[{candidate.id}] {candidate.text}" for candidate in task.candidates)
    return f"{INSTRUCTIONS}\n\nQUESTION\n{task.question}\n\nSEARCH RESULTS\n{results}\n"


def run_task(
    task: DiscriminationTask, model: str, adapter: CompletionAdapter
) -> DiscriminationAttempt:
    """Put one candidate set to the model and record what came back.

    A reply with no text is recorded as a failure rather than as an empty
    answer. The first task learned that counting silence as a decision puts a
    model that answered nothing into mid-table.
    """
    try:
        turn = adapter.complete(build_prompt(task))
    except Exception as error:
        return DiscriminationAttempt(
            task_id=task.id, model=model, error=f"{type(error).__name__}: {error}"
        )

    attempt = DiscriminationAttempt(
        task_id=task.id,
        model=model,
        reply=turn.answer,
        tokens_in=turn.tokens_in,
        tokens_out=turn.tokens_out,
        reasoning_tokens=turn.reasoning_tokens,
        cached_tokens=turn.cached_tokens,
        latency_s=turn.latency_s,
        stop_reason=turn.stop_reason,
    )
    if not turn.answer.strip():
        return attempt.model_copy(
            update={
                "error": "empty reply"
                + (f" (stop reason {turn.stop_reason!r})" if turn.stop_reason else "")
            }
        )
    return attempt


def run_tasks(
    tasks: Sequence[DiscriminationTask],
    model: str,
    adapter: CompletionAdapter,
    *,
    out_path: Path | None = None,
    on_item: ProgressHook | None = None,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[DiscriminationAttempt]:
    """Run a task set, writing each attempt the moment it lands."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    attempts: list[DiscriminationAttempt] = []
    writing = threading.Lock()
    done = 0

    def record(task: DiscriminationTask, attempt: DiscriminationAttempt) -> None:
        nonlocal done
        with writing:
            done += 1
            if out_path is not None:
                append_line(out_path, attempt.model_dump_json())
            attempts.append(attempt)
            if on_item is not None:
                on_item(done, len(tasks), task, attempt)

    if concurrency <= 1:
        for task in tasks:
            record(task, run_task(task, model, adapter))
        return attempts

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(run_task, task, model, adapter): task for task in tasks}
        for future in as_completed(futures):
            record(futures[future], future.result())

    return attempts


def completed_task_ids(path: Path) -> set[str]:
    """Items already answered, so a run can resume. A failure is not answered."""
    if not path.exists():
        return set()
    from llmsearchbench.storage import read_jsonl

    return {
        str(row["task_id"])
        for row in read_jsonl(path)
        if row.get("task_id") and not row.get("error")
    }
