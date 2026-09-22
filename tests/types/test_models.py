"""What the Pydantic models refuse.

Validation moved out of the CLI and into the types, so these tests are where
the guarantees live: a bad artefact fails at load, with the field named.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llmsearchbench.types import Category, Manifest, RunRecord, Task, Verdict


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
