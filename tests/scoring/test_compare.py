"""Reproduction diffing — the thing that decides whether someone's rerun matched."""

from __future__ import annotations

from llmsearchbench.scoring import DEFAULT_TOLERANCES, diff_summaries
from tests.conftest import make_row, make_summary


class TestMatching:
    def test_identical_summaries_match(self) -> None:
        summary = make_summary(make_row())
        report = diff_summaries(summary, summary)
        assert report.matches
        assert report.failures == []

    def test_drift_inside_tolerance_still_matches(self) -> None:
        """At 120 tasks a 1-point accuracy gap is sampling noise, not a broken harness."""
        reference = make_summary(make_row(accuracy=0.80))
        actual = make_summary(make_row(accuracy=0.81))
        assert diff_summaries(actual, reference).matches

    def test_drift_past_tolerance_fails(self) -> None:
        reference = make_summary(make_row(accuracy=0.80))
        actual = make_summary(make_row(accuracy=0.70))
        report = diff_summaries(actual, reference)
        assert not report.matches
        assert [d.metric for d in report.failures] == ["accuracy"]

    def test_drift_exactly_at_the_tolerance_is_accepted(self) -> None:
        reference = make_summary(make_row(accuracy=0.80))
        actual = make_summary(make_row(accuracy=0.80 + DEFAULT_TOLERANCES["accuracy"]))
        assert diff_summaries(actual, reference).matches

    def test_a_metric_moving_the_wrong_way_still_fails(self) -> None:
        """Beating the reference by a wide margin is as suspicious as missing it."""
        reference = make_summary(make_row(accuracy=0.70))
        actual = make_summary(make_row(accuracy=0.95))
        assert not diff_summaries(actual, reference).matches


class TestModelSets:
    def test_a_missing_model_fails_the_reproduction(self) -> None:
        reference = make_summary(make_row("a"), make_row("b"))
        actual = make_summary(make_row("a"))
        report = diff_summaries(actual, reference)
        assert report.missing_models == ["b"]
        assert not report.matches

    def test_an_extra_model_is_reported_but_does_not_fail(self) -> None:
        """Evaluating a model the release never covered is a legitimate use."""
        reference = make_summary(make_row("a"))
        actual = make_summary(make_row("a"), make_row("z"))
        report = diff_summaries(actual, reference)
        assert report.extra_models == ["z"]
        assert report.matches

    def test_no_overlap_at_all_fails_loudly(self) -> None:
        report = diff_summaries(make_summary(make_row("x")), make_summary(make_row("y")))
        assert report.missing_models == ["y"]
        assert report.extra_models == ["x"]
        assert not report.matches


class TestCostTolerance:
    def test_cost_drift_does_not_fail_a_reproduction(self) -> None:
        """Provider list prices move on their own; a price cut is not a failed rerun."""
        reference = make_summary(make_row(cost_per_1k=40.0))
        actual = make_summary(make_row(cost_per_1k=4.0))
        assert diff_summaries(actual, reference).matches


class TestRendering:
    def test_a_failure_names_the_model_metric_and_gap(self) -> None:
        reference = make_summary(make_row("gpt-test", accuracy=0.80))
        actual = make_summary(make_row("gpt-test", accuracy=0.60))
        rendered = diff_summaries(actual, reference).render()
        assert "gpt-test" in rendered
        assert "accuracy" in rendered
        assert "-0.2" in rendered

    def test_a_match_says_how_many_models_were_checked(self) -> None:
        summary = make_summary(make_row("a"), make_row("b"))
        assert "2 models" in diff_summaries(summary, summary).render()

    def test_custom_tolerance_overrides_the_default(self) -> None:
        reference = make_summary(make_row(accuracy=0.80))
        actual = make_summary(make_row(accuracy=0.70))
        assert diff_summaries(actual, reference, {"accuracy": 0.2}).matches
