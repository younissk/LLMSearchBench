"""What the Pydantic models refuse.

Validation moved out of the CLI and into the types, so these tests are where
the guarantees live: a bad artefact fails at load, with the field named.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llmsearchbench.types import (
    Category,
    Manifest,
    ResultRow,
    RunRecord,
    Summary,
    Task,
    Verdict,
)
from tests.conftest import make_row, make_summary


class TestFractions:
    @pytest.mark.parametrize("metric", ["accuracy", "citation_f1", "hallucination_rate"])
    def test_a_percentage_is_rejected(self, metric: str) -> None:
        """87.1 instead of 0.871 would render as 8710% on the site."""
        with pytest.raises(ValidationError, match=metric):
            make_row(**{metric: 87.1})

    @pytest.mark.parametrize("metric", ["accuracy", "citation_f1", "hallucination_rate"])
    def test_a_negative_fraction_is_rejected(self, metric: str) -> None:
        with pytest.raises(ValidationError, match=metric):
            make_row(**{metric: -0.01})

    @pytest.mark.parametrize("value", [0.0, 1.0])
    def test_the_bounds_themselves_are_allowed(self, value: float) -> None:
        assert make_row(accuracy=value).accuracy == value


class TestResultRowAliases:
    def test_accepts_the_camel_case_the_site_writes(self) -> None:
        row = ResultRow.model_validate(
            {
                "model": "m",
                "provider": "p",
                "accuracy": 0.8,
                "citationF1": 0.7,
                "hallucinationRate": 0.05,
                "latencyP50": 1.0,
                "costPer1k": 2.0,
                "searchCalls": 3.0,
            }
        )
        assert row.citation_f1 == 0.7
        assert row.cost_per_1k == 2.0

    def test_serialises_back_to_camel_case(self) -> None:
        assert set(make_row().model_dump()) == {
            "model",
            "provider",
            "accuracy",
            "citationF1",
            "hallucinationRate",
            "latencyP50",
            "costPer1k",
            "searchCalls",
        }

    def test_negative_cost_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"cost_per_1k|costPer1k"):
            make_row(cost_per_1k=-1.0)


class TestSummary:
    def test_duplicate_model_rows_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate model rows"):
            make_summary(make_row("a"), make_row("a"))

    def test_an_unexpected_key_is_rejected(self) -> None:
        """A typo'd key should fail loudly, not silently drop a metric."""
        raw = make_summary().model_dump()
        raw["taskCounts"] = 120
        with pytest.raises(ValidationError, match="taskCounts"):
            Summary.model_validate(raw)

    def test_row_lookup(self) -> None:
        summary = make_summary(make_row("a"), make_row("b"))
        assert summary.row("b") is not None
        assert summary.row("absent") is None

    def test_models_are_frozen(self) -> None:
        """A row handed to a chart must not be mutable behind the caller's back."""
        with pytest.raises(ValidationError):
            make_row().accuracy = 0.99  # type: ignore[misc]


class TestTask:
    def test_category_is_a_closed_set(self) -> None:
        with pytest.raises(ValidationError, match="category"):
            Task(
                id="t-001",
                question="q",
                gold_answer="a",
                gold_sources=[],
                category="trick-question",  # type: ignore[arg-type]
            )

    def test_is_negative(self) -> None:
        task = Task(
            id="t-001",
            question="q",
            gold_answer="No reliable source says so.",
            gold_sources=[],
            category=Category.NEGATIVE,
        )
        assert task.is_negative

    def test_an_empty_id_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="id"):
            Task(
                id="",
                question="q",
                gold_answer="a",
                gold_sources=[],
                category=Category.SINGLE_HOP,
            )


class TestRunRecord:
    def test_negative_token_counts_are_rejected(self) -> None:
        """A negative count would sail straight into a published cost."""
        with pytest.raises(ValidationError, match="tokens_in"):
            RunRecord(
                task_id="t-001",
                model="m",
                answer="a",
                citations=[],
                verdict=Verdict.CORRECT,
                tokens_in=-1,
                tokens_out=0,
                latency_s=0.0,
                search_calls=0,
            )

    def test_is_judged(self) -> None:
        def record(verdict: Verdict) -> RunRecord:
            return RunRecord(
                task_id="t-001",
                model="m",
                answer="a",
                citations=[],
                verdict=verdict,
                tokens_in=0,
                tokens_out=0,
                latency_s=0.0,
                search_calls=0,
            )

        assert record(Verdict.CORRECT).is_judged
        assert record(Verdict.INCORRECT).is_judged
        assert not record(Verdict.UNJUDGEABLE).is_judged

    def test_claim_counts_default_to_zero(self) -> None:
        """Runs made before per-claim support existed must still load."""
        record = RunRecord(
            task_id="t-001",
            model="m",
            answer="a",
            citations=[],
            verdict=Verdict.CORRECT,
            tokens_in=0,
            tokens_out=0,
            latency_s=0.0,
            search_calls=0,
        )
        assert record.total_claims == 0


class TestManifest:
    def test_the_judge_model_is_required(self) -> None:
        """The judge is part of a release's identity; a manifest without it pins nothing."""
        with pytest.raises(ValidationError, match="judge_model"):
            Manifest.model_validate(
                {
                    "version": "v0.1.0",
                    "date": "2026-09-22",
                    "harness_commit": "abc1234",
                }
            )

    def test_stays_snake_case_unlike_the_site_facing_models(self) -> None:
        manifest = Manifest(
            version="v0.1.0",
            date="2026-09-22",
            harness_commit="abc1234",
            judge_model="claude-opus-5",
        )
        assert "harness_commit" in manifest.model_dump()
