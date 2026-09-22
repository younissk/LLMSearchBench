"""Scoring the tool-use-correctness task.

Three things are measured, and they are kept apart rather than folded into one
number, because they fail for different reasons and call for different fixes:

1. **Decision** — did the model reach for the search tool when it should have,
   and leave it alone when it should not?
2. **Call quality** — when it did reach, was the call well formed?
3. **Answer** — was the final answer right? Reported second, because a model
   can be right by luck after a wrong decision.

The two no-search buckets are reported separately throughout. Searching a
`memory` item means the model knew the answer and did not trust itself;
searching a `no_tool` item means it reached for retrieval when there was no
fact to retrieve. Averaging those hides which problem a model actually has.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import Field

from llmsearchbench.taskgen.filters import fold
from llmsearchbench.types import BenchModel
from llmsearchbench.types.tooluse import Bucket, ToolUseAttempt, ToolUseTask

#: Search calls allowed per item before the harness stops the model.
DEFAULT_CALL_BUDGET = 6


class CallProblem(StrEnum):
    """What can be wrong with a tool call, independent of whether to make it."""

    #: Asked for a tool that is not the search tool.
    WRONG_TOOL = "wrong-tool"
    #: Arguments did not satisfy the tool schema.
    SCHEMA_ERROR = "schema-error"
    #: Called search with nothing to search for.
    EMPTY_QUERY = "empty-query"
    #: Issued a query already issued for this item — burns budget for nothing.
    DUPLICATE_QUERY = "duplicate-query"
    #: Kept calling past the harness budget.
    OVER_BUDGET = "over-budget"


class TaskOutcome(BenchModel):
    """One model's result on one item."""

    task_id: str
    bucket: Bucket
    adversarial: bool
    expected_search: bool
    searched: bool
    call_count: int = Field(ge=0)
    problems: list[CallProblem] = Field(default_factory=list)
    #: None for `no_tool`, which is open-ended and carries no gold answer.
    answer_correct: bool | None = None

    @property
    def decision_correct(self) -> bool:
        return self.searched == self.expected_search

    @property
    def calls_well_formed(self) -> bool:
        return not self.problems


class BucketScore(BenchModel):
    """Per-bucket decision result."""

    bucket: Bucket
    items: int = Field(ge=0)
    correct_decisions: int = Field(ge=0)

    @property
    def accuracy(self) -> float:
        return self.correct_decisions / self.items if self.items else 0.0


class ToolUseScore(BenchModel):
    """The published result for one model on the tool-use-correctness task."""

    model: str
    items: int = Field(ge=0)

    # --- 1. decision ---
    decision_accuracy: float = Field(ge=0, le=1)
    buckets: list[BucketScore] = Field(default_factory=list)
    #: Searched a `memory` item. A confidence failure.
    over_search_memory: float = Field(ge=0, le=1)
    #: Searched a `no_tool` item. A reflex failure.
    over_search_no_tool: float = Field(ge=0, le=1)
    #: Did not search a `search` item. Answering from memory is a guess here.
    under_search: float = Field(ge=0, le=1)
    #: Decision accuracy restricted to the items worded to bait a search.
    adversarial_accuracy: float = Field(ge=0, le=1)

    # --- 2. call quality ---
    calls_total: int = Field(ge=0)
    items_with_calls: int = Field(ge=0)
    #: Share of calling items whose every call was clean.
    well_formed_rate: float = Field(ge=0, le=1)
    problem_counts: dict[str, int] = Field(default_factory=dict)

    # --- 3. answer ---
    answer_accuracy_memory: float = Field(ge=0, le=1)
    answer_accuracy_search: float = Field(ge=0, le=1)

    def bucket_score(self, bucket: Bucket) -> BucketScore | None:
        return next((b for b in self.buckets if b.bucket is bucket), None)


def answer_matches(answer: str, gold: Sequence[str]) -> bool:
    """Accent- and punctuation-insensitive containment against any gold alias.

    Deliberately lenient: this task is about the tool decision, and a strict
    answer check would turn it into a QA benchmark by the back door.
    """
    folded = fold(answer)
    return any(fold(alias) in folded for alias in gold if alias.strip())


def inspect_calls(
    attempt: ToolUseAttempt,
    *,
    search_tool: str = "search",
    call_budget: int = DEFAULT_CALL_BUDGET,
) -> list[CallProblem]:
    """Everything wrong with how this attempt used the tool."""
    problems: list[CallProblem] = []
    seen: set[str] = set()

    for call in attempt.calls:
        if call.name != search_tool:
            problems.append(CallProblem.WRONG_TOOL)
            continue
        if call.schema_error:
            problems.append(CallProblem.SCHEMA_ERROR)
            continue
        query = call.query.strip()
        if not query:
            problems.append(CallProblem.EMPTY_QUERY)
            continue
        normalised = fold(query)
        if normalised in seen:
            problems.append(CallProblem.DUPLICATE_QUERY)
        seen.add(normalised)

    if len(attempt.calls) > call_budget:
        problems.append(CallProblem.OVER_BUDGET)

    # Order-stable de-duplication: one item reports each problem kind once.
    return list(dict.fromkeys(problems))


def outcome_for(
    task: ToolUseTask,
    attempt: ToolUseAttempt,
    *,
    search_tool: str = "search",
    call_budget: int = DEFAULT_CALL_BUDGET,
) -> TaskOutcome:
    answer_correct: bool | None = None
    if task.bucket is not Bucket.NO_TOOL:
        answer_correct = answer_matches(attempt.answer, task.gold_answer)

    return TaskOutcome(
        task_id=task.id,
        bucket=task.bucket,
        adversarial=task.adversarial,
        expected_search=task.expects_search,
        searched=attempt.searched,
        call_count=len(attempt.calls),
        problems=inspect_calls(attempt, search_tool=search_tool, call_budget=call_budget),
        answer_correct=answer_correct,
    )


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def score(
    model: str,
    tasks: Sequence[ToolUseTask],
    attempts: Sequence[ToolUseAttempt],
    *,
    search_tool: str = "search",
    call_budget: int = DEFAULT_CALL_BUDGET,
) -> ToolUseScore:
    """Collapse one model's attempts into a published result.

    Every task must have exactly one attempt: a missing attempt is a broken run,
    not a zero, and silently scoring it as a failed decision would understate
    the model rather than surface the bug.
    """
    by_id = {attempt.task_id: attempt for attempt in attempts}
    missing = [task.id for task in tasks if task.id not in by_id]
    if missing:
        raise ValueError(
            f"{len(missing)} task(s) have no attempt from {model!r}, first few: {missing[:3]}"
        )

    outcomes = [
        outcome_for(task, by_id[task.id], search_tool=search_tool, call_budget=call_budget)
        for task in tasks
    ]

    buckets = [
        BucketScore(
            bucket=bucket,
            items=sum(1 for o in outcomes if o.bucket is bucket),
            correct_decisions=sum(
                1 for o in outcomes if o.bucket is bucket and o.decision_correct
            ),
        )
        for bucket in Bucket
    ]

    def over_search(bucket: Bucket) -> float:
        pool = [o for o in outcomes if o.bucket is bucket]
        return _rate(sum(1 for o in pool if o.searched), len(pool))

    search_pool = [o for o in outcomes if o.bucket is Bucket.SEARCH]
    adversarial = [o for o in outcomes if o.adversarial]
    calling = [o for o in outcomes if o.call_count]

    problem_counts: dict[str, int] = {}
    for outcome in outcomes:
        for problem in outcome.problems:
            problem_counts[problem.value] = problem_counts.get(problem.value, 0) + 1

    def answer_accuracy(bucket: Bucket) -> float:
        pool = [o for o in outcomes if o.bucket is bucket and o.answer_correct is not None]
        return _rate(sum(1 for o in pool if o.answer_correct), len(pool))

    return ToolUseScore(
        model=model,
        items=len(outcomes),
        decision_accuracy=_rate(sum(1 for o in outcomes if o.decision_correct), len(outcomes)),
        buckets=buckets,
        over_search_memory=over_search(Bucket.MEMORY),
        over_search_no_tool=over_search(Bucket.NO_TOOL),
        under_search=_rate(sum(1 for o in search_pool if not o.searched), len(search_pool)),
        adversarial_accuracy=_rate(
            sum(1 for o in adversarial if o.decision_correct), len(adversarial)
        ),
        calls_total=sum(o.call_count for o in outcomes),
        items_with_calls=len(calling),
        well_formed_rate=_rate(sum(1 for o in calling if o.calls_well_formed), len(calling)),
        problem_counts=dict(sorted(problem_counts.items())),
        answer_accuracy_memory=answer_accuracy(Bucket.MEMORY),
        answer_accuracy_search=answer_accuracy(Bucket.SEARCH),
    )
