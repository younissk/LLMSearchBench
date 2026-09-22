"""Scoring the tool-use-correctness task."""

from __future__ import annotations

import pytest

from llmsearchbench.scoring.tooluse import (
    CallProblem,
    answer_matches,
    inspect_calls,
    outcome_for,
    score,
)
from llmsearchbench.types.tooluse import Bucket, ToolCall, ToolUseAttempt, ToolUseTask


def task(
    task_id: str = "t1",
    bucket: Bucket = Bucket.SEARCH,
    gold: list[str] | None = None,
    adversarial: bool = False,
) -> ToolUseTask:
    return ToolUseTask(
        id=task_id,
        bucket=bucket,
        prompt="a prompt",
        gold_answer=gold
        if gold is not None
        else ([] if bucket is Bucket.NO_TOOL else ["Paris"]),
        source="test",
        subcategory="test",
        adversarial=adversarial,
    )


def attempt(
    task_id: str = "t1",
    answer: str = "",
    queries: list[str] | None = None,
    calls: list[ToolCall] | None = None,
) -> ToolUseAttempt:
    if calls is None:
        calls = [ToolCall(name="search", arguments={"query": q}) for q in (queries or [])]
    return ToolUseAttempt(task_id=task_id, model="m", answer=answer, calls=calls)


class TestAnswerMatches:
    def test_ignores_accents_and_case(self) -> None:
        assert answer_matches("The composer was Leoš Janáček.", ["Leos Janacek"])

    def test_requires_the_alias_to_appear(self) -> None:
        assert not answer_matches("I am not sure.", ["Paris"])

    def test_any_alias_is_enough(self) -> None:
        assert answer_matches("It is Valletta.", ["Il-Belt Valletta", "Valletta"])

    def test_blank_aliases_are_ignored(self) -> None:
        """TriviaQA alias lists contain empty strings, which match everything."""
        assert not answer_matches("anything", ["", "  "])


class TestInspectCalls:
    def test_a_clean_call_has_no_problems(self) -> None:
        assert inspect_calls(attempt(queries=["capital of Malta"])) == []

    def test_wrong_tool(self) -> None:
        calls = [ToolCall(name="calculator", arguments={"expr": "2+2"})]
        assert inspect_calls(attempt(calls=calls)) == [CallProblem.WRONG_TOOL]

    def test_schema_error(self) -> None:
        calls = [ToolCall(name="search", arguments={}, schema_error="query is required")]
        assert inspect_calls(attempt(calls=calls)) == [CallProblem.SCHEMA_ERROR]

    def test_empty_query(self) -> None:
        assert inspect_calls(attempt(queries=["   "])) == [CallProblem.EMPTY_QUERY]

    def test_duplicate_query_burns_budget_for_nothing(self) -> None:
        got = inspect_calls(attempt(queries=["same thing", "Same Thing!"]))
        assert got == [CallProblem.DUPLICATE_QUERY]

    def test_distinct_queries_are_not_duplicates(self) -> None:
        assert inspect_calls(attempt(queries=["first", "second"])) == []

    def test_over_budget(self) -> None:
        queries = [f"q{i}" for i in range(8)]
        assert CallProblem.OVER_BUDGET in inspect_calls(attempt(queries=queries))

    def test_each_problem_is_reported_once_per_item(self) -> None:
        got = inspect_calls(attempt(queries=["", "", ""]))
        assert got == [CallProblem.EMPTY_QUERY]


class TestOutcome:
    def test_no_tool_items_have_no_answer_verdict(self) -> None:
        out = outcome_for(task(bucket=Bucket.NO_TOOL), attempt(answer="a poem"))
        assert out.answer_correct is None

    def test_decision_correct_when_it_searched_a_search_item(self) -> None:
        out = outcome_for(task(bucket=Bucket.SEARCH), attempt(queries=["x"]))
        assert out.decision_correct

    def test_decision_wrong_when_it_searched_a_memory_item(self) -> None:
        out = outcome_for(task(bucket=Bucket.MEMORY), attempt(queries=["x"]))
        assert not out.decision_correct


class TestScore:
    def build(self) -> tuple[list[ToolUseTask], list[ToolUseAttempt]]:
        tasks = [
            task("mem-ok", Bucket.MEMORY),
            task("mem-oversearch", Bucket.MEMORY),
            task("sea-ok", Bucket.SEARCH),
            task("sea-undersearch", Bucket.SEARCH),
            task("nt-ok", Bucket.NO_TOOL, adversarial=True),
            task("nt-oversearch", Bucket.NO_TOOL, adversarial=True),
        ]
        attempts = [
            attempt("mem-ok", answer="Paris"),
            attempt("mem-oversearch", answer="Paris", queries=["capital of France"]),
            attempt("sea-ok", answer="Paris", queries=["something recent"]),
            attempt("sea-undersearch", answer="a guess"),
            attempt("nt-ok", answer="a poem"),
            attempt("nt-oversearch", answer="a poem", queries=["how to write a poem"]),
        ]
        return tasks, attempts

    def test_decision_accuracy(self) -> None:
        tasks, attempts = self.build()
        result = score("m", tasks, attempts)
        assert result.decision_accuracy == pytest.approx(3 / 6)

    def test_the_two_over_search_rates_are_reported_apart(self) -> None:
        """Searching a known fact and searching a poem request are different bugs."""
        tasks, attempts = self.build()
        result = score("m", tasks, attempts)
        assert result.over_search_memory == pytest.approx(0.5)
        assert result.over_search_no_tool == pytest.approx(0.5)

    def test_under_search(self) -> None:
        tasks, attempts = self.build()
        assert score("m", tasks, attempts).under_search == pytest.approx(0.5)

    def test_per_bucket_scores(self) -> None:
        tasks, attempts = self.build()
        result = score("m", tasks, attempts)
        for bucket in Bucket:
            assert result.bucket_score(bucket) is not None
            assert result.bucket_score(bucket).accuracy == pytest.approx(0.5)  # type: ignore[union-attr]

    def test_adversarial_accuracy_is_measured_separately(self) -> None:
        tasks, attempts = self.build()
        assert score("m", tasks, attempts).adversarial_accuracy == pytest.approx(0.5)

    def test_answer_accuracy_split_by_bucket(self) -> None:
        tasks, attempts = self.build()
        result = score("m", tasks, attempts)
        assert result.answer_accuracy_memory == pytest.approx(1.0)
        assert result.answer_accuracy_search == pytest.approx(0.5)

    def test_call_quality_counts_only_items_that_called(self) -> None:
        tasks, attempts = self.build()
        result = score("m", tasks, attempts)
        assert result.items_with_calls == 3
        assert result.calls_total == 3
        assert result.well_formed_rate == pytest.approx(1.0)

    def test_malformed_calls_are_counted(self) -> None:
        tasks = [task("sea", Bucket.SEARCH)]
        bad = attempt("sea", calls=[ToolCall(name="calculator", arguments={})])
        result = score("m", tasks, [bad])
        assert result.well_formed_rate == pytest.approx(0.0)
        assert result.problem_counts == {"wrong-tool": 1}

    def test_a_missing_attempt_is_an_error_not_a_zero(self) -> None:
        """A broken run should surface as a bug, not as a model that scored badly."""
        tasks, attempts = self.build()
        with pytest.raises(ValueError, match="no attempt"):
            score("m", tasks, attempts[:-1])
