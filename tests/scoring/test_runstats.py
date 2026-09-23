"""What a run cost, in money, tokens, and time."""

from __future__ import annotations

import pytest

from llmsearchbench.scoring.runstats import compute, percentile
from llmsearchbench.types.tooluse import Bucket, ToolCall, ToolUseAttempt, ToolUseTask

#: qwen3.5-27b is priced at $0.195 / $1.560 per million.
PRICED_MODEL = "qwen/qwen3.5-27b"
PRICE_IN, PRICE_OUT = 0.195, 1.560


def task(task_id: str, bucket: Bucket = Bucket.SEARCH) -> ToolUseTask:
    return ToolUseTask(
        id=task_id,
        bucket=bucket,
        prompt="a prompt",
        gold_answer=[] if bucket is Bucket.NO_TOOL else ["x"],
        source="test",
        subcategory="test",
    )


def attempt(
    task_id: str,
    *,
    tokens_in: int = 1000,
    tokens_out: int = 500,
    reasoning: int = 0,
    latency: float = 2.0,
    calls: int = 0,
    answer: str = "an answer",
) -> ToolUseAttempt:
    return ToolUseAttempt(
        task_id=task_id,
        model=PRICED_MODEL,
        answer=answer,
        calls=[ToolCall(name="search", arguments={"query": f"q{i}"}) for i in range(calls)],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        reasoning_tokens=reasoning,
        latency_s=latency,
    )


class TestPercentile:
    def test_picks_a_real_observation(self) -> None:
        """Interpolating on a 30-item run would be false precision."""
        assert percentile([1, 2, 3, 4, 5], 0.95) == 5

    def test_median_ish(self) -> None:
        assert percentile([1, 2, 3, 4], 0.5) == 2

    def test_empty(self) -> None:
        assert percentile([], 0.95) == 0.0


class TestCost:
    def test_totals_use_the_catalogue_price(self) -> None:
        stats = compute(PRICED_MODEL, [task("a")], [attempt("a")])
        expected = 1000 / 1e6 * PRICE_IN + 500 / 1e6 * PRICE_OUT
        assert stats.cost.total_usd == pytest.approx(expected)

    def test_an_unpriced_model_reports_zero_and_says_so(self) -> None:
        """Publishing a cost of zero as if it were real would be a lie."""
        stats = compute("not-in-the-catalogue", [task("a")], [attempt("a")])
        assert not stats.cost.priced
        assert stats.cost.total_usd == 0.0

    def test_wasted_spend_counts_only_needless_searches(self) -> None:
        """Searching a memory or no_tool item buys nothing; that spend is waste."""
        tasks = [
            task("mem", Bucket.MEMORY),
            task("nt", Bucket.NO_TOOL),
            task("sea", Bucket.SEARCH),
        ]
        attempts = [
            attempt("mem", calls=1),  # wrong: knew it already
            attempt("nt", calls=1),  # wrong: nothing to find
            attempt("sea", calls=1),  # right: needed the tool
        ]
        stats = compute(PRICED_MODEL, tasks, attempts)
        per_item = 1000 / 1e6 * PRICE_IN + 500 / 1e6 * PRICE_OUT
        assert stats.cost.wasted_usd == pytest.approx(2 * per_item)
        assert stats.cost.wasted_share == pytest.approx(2 / 3)

    def test_a_model_that_never_searches_wastes_nothing(self) -> None:
        tasks = [task("mem", Bucket.MEMORY), task("nt", Bucket.NO_TOOL)]
        stats = compute(PRICED_MODEL, tasks, [attempt("mem"), attempt("nt")])
        assert stats.cost.wasted_usd == 0.0

    def test_cost_per_right_decision(self) -> None:
        tasks = [task("a", Bucket.MEMORY), task("b", Bucket.MEMORY)]
        attempts = [attempt("a"), attempt("b", calls=1)]  # one right, one wrong
        stats = compute(PRICED_MODEL, tasks, attempts)
        assert stats.cost.usd_per_correct_decision == pytest.approx(stats.cost.total_usd)


class TestTokens:
    def test_totals_and_means(self) -> None:
        stats = compute(
            PRICED_MODEL,
            [task("a"), task("b")],
            [attempt("a", tokens_out=100), attempt("b", tokens_out=300)],
        )
        assert stats.tokens.output_total == 400
        assert stats.tokens.output_mean == pytest.approx(200)
        assert stats.tokens.output_max == 300

    def test_reasoning_is_reported_as_a_share_of_output(self) -> None:
        """Thinking is billed as output, so it is inside the output total."""
        stats = compute(
            PRICED_MODEL, [task("a")], [attempt("a", tokens_out=1000, reasoning=800)]
        )
        assert stats.tokens.reasoning_total == 800
        assert stats.tokens.reasoning_share == pytest.approx(0.8)

    def test_reasoning_share_is_zero_when_nothing_thought(self) -> None:
        stats = compute(PRICED_MODEL, [task("a")], [attempt("a")])
        assert stats.tokens.reasoning_share == 0.0
        assert stats.items_with_reasoning == 0


class TestTime:
    def test_p95_and_max_catch_the_stall_a_mean_hides(self) -> None:
        tasks = [task(str(i)) for i in range(10)]
        attempts = [attempt(str(i), latency=1.0) for i in range(9)]
        attempts.append(attempt("9", latency=120.0))
        stats = compute(PRICED_MODEL, tasks, attempts)
        assert stats.time.median_s == pytest.approx(1.0)
        assert stats.time.max_s == pytest.approx(120.0)

    def test_throughput(self) -> None:
        tasks = [task("a"), task("b")]
        attempts = [attempt("a", latency=30.0), attempt("b", latency=30.0)]
        stats = compute(PRICED_MODEL, tasks, attempts)
        assert stats.items_per_minute == pytest.approx(2.0)


class TestBuckets:
    def test_effort_is_broken_out_per_bucket(self) -> None:
        """The interesting question is whether it burns tokens on the easy ones."""
        tasks = [task("m", Bucket.MEMORY), task("n", Bucket.NO_TOOL)]
        attempts = [attempt("m", tokens_out=100), attempt("n", tokens_out=900)]
        stats = compute(PRICED_MODEL, tasks, attempts)
        by_bucket = {b.bucket: b for b in stats.buckets}
        assert by_bucket[Bucket.MEMORY].tokens_out_mean == pytest.approx(100)
        assert by_bucket[Bucket.NO_TOOL].tokens_out_mean == pytest.approx(900)

    def test_empty_buckets_are_omitted(self) -> None:
        stats = compute(PRICED_MODEL, [task("a", Bucket.MEMORY)], [attempt("a")])
        assert [b.bucket for b in stats.buckets] == [Bucket.MEMORY]


class TestCounters:
    def test_attempts_without_a_matching_task_are_ignored(self) -> None:
        """A stale attempts file should not inflate the totals."""
        stats = compute(PRICED_MODEL, [task("a")], [attempt("a"), attempt("ghost")])
        assert stats.items == 1

    def test_failed_items_are_counted(self) -> None:
        broken = attempt("a").model_copy(update={"error": "provider timed out"})
        stats = compute(PRICED_MODEL, [task("a")], [broken])
        assert stats.failed_items == 1


class TestCallCounts:
    def test_search_calls_are_totalled(self) -> None:
        tasks = [task("a"), task("b")]
        attempts = [attempt("a", calls=1), attempt("b")]
        assert compute(PRICED_MODEL, tasks, attempts).search_calls_total == 1


class TestFailuresAreNotScored:
    """A provider error produced no decision and must not read as one."""

    def test_failed_attempts_are_excluded_from_the_totals(self) -> None:
        broken = attempt("a").model_copy(update={"error": "404: no endpoints"})
        stats = compute(PRICED_MODEL, [task("a"), task("b")], [broken, attempt("b")])
        assert stats.items == 1
        assert stats.failed_items == 1

    def test_a_run_that_failed_everything_scores_nothing(self) -> None:
        """Counting a failure as 'chose not to search' is right on two buckets
        out of three, which once put a totally broken run mid-table."""
        broken = [attempt(name).model_copy(update={"error": "404"}) for name in ("a", "b")]
        stats = compute(PRICED_MODEL, [task("a"), task("b")], broken)
        assert stats.items == 0
        assert stats.failed_items == 2
        assert stats.cost.total_usd == 0.0
