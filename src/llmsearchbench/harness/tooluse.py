"""Running the tool-use-correctness task.

One prompt, one decision, one record. The loop is deliberately thin: the
scoring lives in `llmsearchbench.scoring.tooluse`, and everything this module
writes is raw observation — what the model said, and every call it made.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from llmsearchbench.harness.config import HarnessConfig
from llmsearchbench.harness.protocols import SearchBackend
from llmsearchbench.storage import append_line
from llmsearchbench.types.tooluse import ToolCall, ToolUseAttempt, ToolUseTask

#: Called after each item with (index, total, task, attempt).
ProgressHook = Callable[[int, int, ToolUseTask, ToolUseAttempt], None]


class PromptAdapter(Protocol):
    """What the run loop needs from a provider adapter.

    Narrower than the QA `ModelAdapter`: this task hands over a bare prompt and
    wants the call log back, not a structured answer.
    """

    def answer(
        self, prompt: str, backend: SearchBackend, config: HarnessConfig
    ) -> tuple[str, list[ToolCall], int, int, float]: ...


def run_task(
    task: ToolUseTask,
    model: str,
    adapter: PromptAdapter,
    backend: SearchBackend,
    config: HarnessConfig,
) -> ToolUseAttempt:
    """Put one prompt to the model and record what it did."""
    answer, calls, tokens_in, tokens_out, latency = adapter.answer(task.prompt, backend, config)
    return ToolUseAttempt(
        task_id=task.id,
        model=model,
        answer=answer,
        calls=calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_s=latency,
    )


def run_tasks(
    tasks: Sequence[ToolUseTask],
    model: str,
    adapter: PromptAdapter,
    backend: SearchBackend,
    config: HarnessConfig,
    *,
    out_path: Path | None = None,
    on_item: ProgressHook | None = None,
) -> list[ToolUseAttempt]:
    """Run a whole task set, writing each attempt as it lands.

    Appending per item rather than at the end means an interrupted run keeps
    everything it already paid for — and these runs cost real money.
    """
    attempts: list[ToolUseAttempt] = []
    for index, task in enumerate(tasks, start=1):
        attempt = run_task(task, model, adapter, backend, config)
        if out_path is not None:
            append_line(out_path, attempt.model_dump_json())
        if on_item is not None:
            on_item(index, len(tasks), task, attempt)
        attempts.append(attempt)
    return attempts


def completed_task_ids(path: Path) -> set[str]:
    """Task ids already recorded in an attempts file, so a run can resume."""
    if not path.exists():
        return set()
    from llmsearchbench.storage import read_jsonl

    return {str(row["task_id"]) for row in read_jsonl(path) if "task_id" in row}
