"""Metric behaviour, especially at the edges that decide whether a model is trustworthy."""

from __future__ import annotations

import pytest

from llmsearchbench.scoring import (
    aggregate,
    citation_f1,
    cost_per_1k,
    unjudgeable_share,
    unsupported_claim_rate,
)
from llmsearchbench.types import RunRecord, Verdict
from tests.conftest import make_record

GOLD = ["https://example.org/a", "https://example.org/b"]


class TestCitationF1:
    def test_exact_match_scores_one(self) -> None:
        assert citation_f1(GOLD, GOLD) == pytest.approx(1.0)

    def test_citing_nothing_scores_zero(self) -> None:
        assert citation_f1([], GOLD) == 0.0

    def test_shotgunning_sources_is_penalised(self) -> None:
        """Citing ten URLs to catch both right ones must score below citing two."""
        precise = citation_f1(GOLD, GOLD)
        shotgun = citation_f1([*GOLD, *(f"https://noise.example/{i}" for i in range(8))], GOLD)
        assert shotgun < precise
        assert shotgun == pytest.approx(2 * (2 / 10) * 1.0 / ((2 / 10) + 1.0))

    def test_half_recall(self) -> None:
        assert citation_f1(["https://example.org/a"], GOLD) == pytest.approx(2 / 3)

    def test_no_overlap_scores_zero(self) -> None:
        assert citation_f1(["https://other.example/x"], GOLD) == 0.0

    def test_negative_task_with_no_citations_scores_one(self) -> None:
        """A task with no gold sources is satisfied by citing nothing."""
        assert citation_f1([], []) == 1.0

    def test_negative_task_that_cites_anyway_scores_zero(self) -> None:
        assert citation_f1(["https://example.org/a"], []) == 0.0

    def test_duplicate_citations_do_not_inflate_precision(self) -> None:
        duplicated = ["https://example.org/a"] * 5
        assert citation_f1(duplicated, GOLD) == citation_f1(["https://example.org/a"], GOLD)


class TestUnsupportedClaimRate:
    def test_counts_share_of_atomic_claims(self) -> None:
        record = make_record(unsupported_claims=1, total_claims=4)
        assert unsupported_claim_rate(record) == pytest.approx(0.25)

    def test_answer_with_no_claims_is_not_a_division_error(self) -> None:
        record = make_record(unsupported_claims=0, total_claims=0)
        assert unsupported_claim_rate(record) == 0.0


class TestCost:
    def test_scales_per_task_cost_to_one_thousand_tasks(self) -> None:
        records = [make_record(tokens_in=1_000_000, tokens_out=0)]
        assert cost_per_1k(records, price_in_per_mtok=3.0, price_out_per_mtok=15.0) == (
            pytest.approx(3000.0)
        )

    def test_output_tokens_are_priced_separately(self) -> None:
        records = [make_record(tokens_in=0, tokens_out=1_000_000)]
        assert cost_per_1k(records, price_in_per_mtok=3.0, price_out_per_mtok=15.0) == (
            pytest.approx(15_000.0)
        )

    def test_empty_run_costs_nothing(self) -> None:
        assert cost_per_1k([], price_in_per_mtok=3.0, price_out_per_mtok=15.0) == 0.0


class TestAggregate:
    def test_accuracy_counts_correct_over_judged(
        self, records: list[RunRecord], gold_sources: dict[str, list[str]]
    ) -> None:
        row = aggregate(
            "test-model",
            "Test Provider",
            records,
            gold_sources,
            price_in_per_mtok=3.0,
            price_out_per_mtok=15.0,
        )
        assert row.accuracy == pytest.approx(2 / 3)

    def test_unjudgeable_records_leave_the_accuracy_denominator(
        self, gold_sources: dict[str, list[str]]
    ) -> None:
        """An unjudgeable task must not count as wrong — that would punish the model
        for a broken task."""
        records = [
            make_record("t-001", verdict=Verdict.CORRECT),
            make_record("t-002", verdict=Verdict.UNJUDGEABLE),
        ]
        row = aggregate(
            "test-model",
            "Test Provider",
            records,
            gold_sources,
            price_in_per_mtok=3.0,
            price_out_per_mtok=15.0,
        )
        assert row.accuracy == pytest.approx(1.0)

    def test_latency_is_the_median_not_the_mean(
        self, gold_sources: dict[str, list[str]]
    ) -> None:
        records = [
            make_record("t-001", latency_s=1.0),
            make_record("t-002", latency_s=2.0),
            make_record("t-003", latency_s=300.0),  # one stall must not move the figure
        ]
        row = aggregate(
            "test-model",
            "Test Provider",
            records,
            gold_sources,
            price_in_per_mtok=0.0,
            price_out_per_mtok=0.0,
        )
        assert row.latency_p50 == pytest.approx(2.0)

    def test_citation_f1_averages_over_every_task_not_just_answered_ones(
        self, records: list[RunRecord], gold_sources: dict[str, list[str]]
    ) -> None:
        row = aggregate(
            "test-model",
            "Test Provider",
            records,
            gold_sources,
            price_in_per_mtok=0.0,
            price_out_per_mtok=0.0,
        )
        # t-001 cites one of two gold sources (2/3), t-002 cites nothing (0),
        # t-003 is a negative task answered with no citations (1).
        assert row.citation_f1 == pytest.approx((2 / 3 + 0.0 + 1.0) / 3)

    def test_all_unjudgeable_does_not_crash(self, gold_sources: dict[str, list[str]]) -> None:
        records = [make_record("t-001", verdict=Verdict.UNJUDGEABLE)]
        row = aggregate(
            "test-model",
            "Test Provider",
            records,
            gold_sources,
            price_in_per_mtok=0.0,
            price_out_per_mtok=0.0,
        )
        assert row.accuracy == 0.0

    def test_empty_record_set_is_an_error_not_a_zero_row(
        self, gold_sources: dict[str, list[str]]
    ) -> None:
        """A model with no records must not silently publish as 0% accurate."""
        with pytest.raises(ValueError, match="no records"):
            aggregate(
                "test-model",
                "Test Provider",
                [],
                gold_sources,
                price_in_per_mtok=0.0,
                price_out_per_mtok=0.0,
            )


class TestUnjudgeableShare:
    def test_share_above_the_limit_is_detectable(self) -> None:
        records = [make_record(f"t-{i:03d}", verdict=Verdict.CORRECT) for i in range(97)]
        records += [
            make_record(f"t-{i:03d}", verdict=Verdict.UNJUDGEABLE) for i in range(97, 100)
        ]
        assert unjudgeable_share(records) == pytest.approx(0.03)

    def test_empty_run_is_zero(self) -> None:
        assert unjudgeable_share([]) == 0.0
