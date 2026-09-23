"""Running the tool-use-correctness task.

One prompt, one response, one record. Nothing is executed on the model's
behalf: the tool is offered, and whether it was reached for is the measurement.

Items are independent, so they run concurrently. Serially, a 360-item run is
dominated by the no-tool bucket, where the model writes a real answer — those
items take twenty seconds each against three for the rest.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Protocol

from llmsearchbench.harness.adapters import Turn
from llmsearchbench.storage import append_line
from llmsearchbench.types.tooluse import ToolUseAttempt, ToolUseTask

#: Called after each item with (done, total, task, attempt).
ProgressHook = Callable[[int, int, ToolUseTask, ToolUseAttempt], None]

#: Parallel requests. Enough to hide latency, low enough not to trip a
#: provider's rate limit on a default account.
DEFAULT_CONCURRENCY = 8


class PromptAdapter(Protocol):
    """What the run loop needs from a provider adapter."""

    def answer(self, prompt: str, temperature: float = 0.0) -> Turn: ...


def run_task(task: ToolUseTask, model: str, adapter: PromptAdapter) -> ToolUseAttempt:
    """Put one prompt to the model and record what it did.

    A failed item is recorded with its error rather than raised. One provider
    hiccup 300 items into a run should not throw away the run.
    """
    try:
        turn = adapter.answer(task.prompt)
    except Exception as error:
        return ToolUseAttempt(
            task_id=task.id,
            model=model,
            error=f"{type(error).__name__}: {error}",
        )

    # A reply with no text and no call is not a decision not to search — it is
    # nothing. Two ways to get one, both seen in real runs: a model that spent
    # its whole budget thinking (`finish_reason: length`), and one that
    # returned an empty message. Scoring either as "chose not to search" would
    # credit it on two buckets out of three for having said nothing at all.
    if not turn.calls and not turn.answer.strip():
        return ToolUseAttempt(
            task_id=task.id,
            model=model,
            tokens_in=turn.tokens_in,
            tokens_out=turn.tokens_out,
            reasoning_tokens=turn.reasoning_tokens,
            cached_tokens=turn.cached_tokens,
            latency_s=turn.latency_s,
            stop_reason=turn.stop_reason,
            tool_protocol=turn.tool_protocol,
            error=(
                "no answer and no tool call"
                + (f" (stop reason {turn.stop_reason!r})" if turn.stop_reason else "")
            ),
        )

    return ToolUseAttempt(
        task_id=task.id,
        model=model,
        answer=turn.answer,
        calls=turn.calls,
        tokens_in=turn.tokens_in,
        tokens_out=turn.tokens_out,
        reasoning_tokens=turn.reasoning_tokens,
        cached_tokens=turn.cached_tokens,
        latency_s=turn.latency_s,
        stop_reason=turn.stop_reason,
        tool_protocol=turn.tool_protocol,
    )


def run_tasks(
    tasks: Sequence[ToolUseTask],
    model: str,
    adapter: PromptAdapter,
    *,
    out_path: Path | None = None,
    on_item: ProgressHook | None = None,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[ToolUseAttempt]:
    """Run a whole task set, writing each attempt the moment it lands.

    Writing per item rather than at the end means an interrupted run keeps
    everything it already paid for. Order in the file follows completion, not
    the task set; resuming matches on task id, so that does not matter.
    """
    attempts: list[ToolUseAttempt] = []
    writing = threading.Lock()
    done = 0

    def record(task: ToolUseTask, attempt: ToolUseAttempt) -> None:
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
    """Task ids already answered, so a run can resume.

    An item that failed does not count as done: a rerun should retry it, which
    is what makes a transient provider error recoverable rather than permanent.
    """
    if not path.exists():
        return set()
    from llmsearchbench.storage import read_jsonl

    return {
        str(row["task_id"])
        for row in read_jsonl(path)
        if row.get("task_id") and not row.get("error")
    }
