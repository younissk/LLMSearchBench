"""What a run cost, in money, tokens, and time.

Separate from the three correctness measurements on purpose. These numbers say
nothing about whether a model is any good — they say what it spent finding out.

Everything here is derived from the recorded attempts at scoring time rather
than stored, so correcting a price does not mean re-running anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median

from pydantic import Field

from llmsearchbench.providers import UnknownModelError, get_model
from llmsearchbench.types import BenchModel
from llmsearchbench.types.tooluse import Bucket, ToolUseAttempt, ToolUseTask


def percentile(values: Sequence[float], fraction: float) -> float:
    """Nearest-rank percentile. Small samples make interpolation false precision."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(fraction * len(ordered)) - 1))
    return ordered[index]


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class TokenStats(BenchModel):
    """Tokens in, out, and how many of the output ones were spent thinking."""

    input_total: int = Field(ge=0)
    output_total: int = Field(ge=0)
    #: Already counted inside `output_total`; reasoning is billed as output.
    reasoning_total: int = Field(default=0, ge=0)
    cached_total: int = Field(default=0, ge=0)

    input_mean: float = Field(ge=0)
    output_mean: float = Field(ge=0)
    reasoning_mean: float = Field(default=0, ge=0)

    output_median: float = Field(ge=0)
    output_p95: float = Field(ge=0)
    output_max: int = Field(ge=0)

    @property
    def total(self) -> int:
        return self.input_total + self.output_total

    @property
    def reasoning_share(self) -> float:
        """How much of the output was thinking rather than answering."""
        return self.reasoning_total / self.output_total if self.output_total else 0.0


class TimeStats(BenchModel):
    """Wall clock per item. Median and p95, because means hide stalls."""

    total_s: float = Field(ge=0)
    mean_s: float = Field(ge=0)
    median_s: float = Field(ge=0)
    p95_s: float = Field(ge=0)
    max_s: float = Field(ge=0)
    #: Mean seconds for items where the model searched, and where it did not.
    mean_s_searched: float = Field(default=0, ge=0)
    mean_s_direct: float = Field(default=0, ge=0)

    @property
    def search_overhead_s(self) -> float:
        """What reaching for the tool costs in time."""
        return self.mean_s_searched - self.mean_s_direct


class CostStats(BenchModel):
    """What the run cost, and how much of it bought nothing."""

    #: False when the model is not priced; every figure below is then zero.
    priced: bool
    total_usd: float = Field(ge=0)
    mean_usd: float = Field(ge=0)
    per_1k_items_usd: float = Field(ge=0)
    input_usd: float = Field(ge=0)
    output_usd: float = Field(ge=0)

    #: Spend on items the model should not have searched at all. Those extra
    #: turns bought nothing: the answer was already known, or there was no fact
    #: to find. This is the dollar value of a bad tool policy.
    wasted_usd: float = Field(ge=0)

    #: Total spend divided by the number of right search-or-not decisions.
    usd_per_correct_decision: float = Field(ge=0)

    @property
    def wasted_share(self) -> float:
        return self.wasted_usd / self.total_usd if self.total_usd else 0.0


class BucketStats(BenchModel):
    """Spend and effort broken out by what kind of prompt it was."""

    bucket: Bucket
    items: int = Field(ge=0)
    tokens_out_mean: float = Field(ge=0)
    reasoning_mean: float = Field(default=0, ge=0)
    latency_mean_s: float = Field(ge=0)
    search_calls_mean: float = Field(ge=0)
    cost_usd: float = Field(ge=0)


class RunStats(BenchModel):
    """Everything a run spent, at every grain worth looking at."""

    model: str
    items: int = Field(ge=0)
    failed_items: int = Field(default=0, ge=0)

    tokens: TokenStats
    time: TimeStats
    cost: CostStats
    buckets: list[BucketStats] = Field(default_factory=list)

    turns_total: int = Field(ge=0)
    turns_mean: float = Field(ge=0)
    search_calls_total: int = Field(ge=0)
    search_calls_mean: float = Field(ge=0)
    #: Items where the model searched more than once.
    items_searching_repeatedly: int = Field(default=0, ge=0)
    #: Items where the provider reported any thinking at all.
    items_with_reasoning: int = Field(default=0, ge=0)

    answer_chars_mean: float = Field(default=0, ge=0)

    @property
    def items_per_minute(self) -> float:
        return self.items / (self.time.total_s / 60) if self.time.total_s else 0.0


def _cost(attempt: ToolUseAttempt, price_in: float, price_out: float) -> float:
    return attempt.tokens_in / 1_000_000 * price_in + attempt.tokens_out / 1_000_000 * price_out


def compute(
    model: str,
    tasks: Sequence[ToolUseTask],
    attempts: Sequence[ToolUseAttempt],
) -> RunStats:
    """Summarise one model's run. Tasks supply the bucket each attempt belongs to."""
    by_id = {task.id: task for task in tasks}
    scored = [attempt for attempt in attempts if attempt.task_id in by_id]

    try:
        spec = get_model(model)
        price_in, price_out = spec.price_in_per_mtok, spec.price_out_per_mtok
        priced = price_in > 0 or price_out > 0
    except UnknownModelError:
        price_in = price_out = 0.0
        priced = False

    latencies = [a.latency_s for a in scored]
    outputs = [a.tokens_out for a in scored]
    searched = [a for a in scored if a.searched]
    direct = [a for a in scored if not a.searched]
    costs = {a.task_id: _cost(a, price_in, price_out) for a in scored}
    total_usd = sum(costs.values())

    # Spend on prompts that never warranted a search in the first place.
    wasted = sum(
        costs[a.task_id] for a in searched if by_id[a.task_id].bucket is not Bucket.SEARCH
    )
    right_calls = sum(
        1 for a in scored if a.searched == (by_id[a.task_id].bucket is Bucket.SEARCH)
    )

    tokens = TokenStats(
        input_total=sum(a.tokens_in for a in scored),
        output_total=sum(outputs),
        reasoning_total=sum(a.reasoning_tokens for a in scored),
        cached_total=sum(a.cached_tokens for a in scored),
        input_mean=_mean([a.tokens_in for a in scored]),
        output_mean=_mean(outputs),
        reasoning_mean=_mean([a.reasoning_tokens for a in scored]),
        output_median=median(outputs) if outputs else 0.0,
        output_p95=percentile(outputs, 0.95),
        output_max=max(outputs) if outputs else 0,
    )

    time_stats = TimeStats(
        total_s=sum(latencies),
        mean_s=_mean(latencies),
        median_s=median(latencies) if latencies else 0.0,
        p95_s=percentile(latencies, 0.95),
        max_s=max(latencies) if latencies else 0.0,
        mean_s_searched=_mean([a.latency_s for a in searched]),
        mean_s_direct=_mean([a.latency_s for a in direct]),
    )

    cost = CostStats(
        priced=priced,
        total_usd=total_usd,
        mean_usd=total_usd / len(scored) if scored else 0.0,
        per_1k_items_usd=(total_usd / len(scored) * 1000) if scored else 0.0,
        input_usd=sum(a.tokens_in for a in scored) / 1_000_000 * price_in,
        output_usd=sum(outputs) / 1_000_000 * price_out,
        wasted_usd=wasted,
        usd_per_correct_decision=total_usd / right_calls if right_calls else 0.0,
    )

    buckets = []
    for bucket in Bucket:
        pool = [a for a in scored if by_id[a.task_id].bucket is bucket]
        if not pool:
            continue
        buckets.append(
            BucketStats(
                bucket=bucket,
                items=len(pool),
                tokens_out_mean=_mean([a.tokens_out for a in pool]),
                reasoning_mean=_mean([a.reasoning_tokens for a in pool]),
                latency_mean_s=_mean([a.latency_s for a in pool]),
                search_calls_mean=_mean([len(a.calls) for a in pool]),
                cost_usd=sum(costs[a.task_id] for a in pool),
            )
        )

    return RunStats(
        model=model,
        items=len(scored),
        failed_items=sum(1 for a in scored if a.failed),
        tokens=tokens,
        time=time_stats,
        cost=cost,
        buckets=buckets,
        turns_total=sum(a.turns for a in scored),
        turns_mean=_mean([a.turns for a in scored]),
        search_calls_total=sum(len(a.calls) for a in scored),
        search_calls_mean=_mean([len(a.calls) for a in scored]),
        items_searching_repeatedly=sum(1 for a in scored if len(a.calls) > 1),
        items_with_reasoning=sum(1 for a in scored if a.reasoning_tokens > 0),
        answer_chars_mean=_mean([a.answer_chars for a in scored]),
    )
