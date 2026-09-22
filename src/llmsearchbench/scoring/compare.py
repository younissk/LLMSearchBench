"""Comparing a local reproduction against a published release."""

from __future__ import annotations

import math
from dataclasses import dataclass

from llmsearchbench.types import ResultRow, Summary

#: Metric name -> absolute tolerance. At 120 tasks the accuracy noise floor is
#: about 3 points, so 0.02 is tight enough to catch a broken harness and loose
#: enough not to fire on sampling noise.
DEFAULT_TOLERANCES: dict[str, float] = {
    "accuracy": 0.02,
    "citation_f1": 0.02,
    "hallucination_rate": 0.02,
    "latency_p50": 5.0,
    "cost_per_1k": 1e9,  # cost tracks provider prices, which move independently
    "search_calls": 0.5,
}

COMPARED_METRICS = tuple(DEFAULT_TOLERANCES)


@dataclass(frozen=True, slots=True)
class MetricDelta:
    model: str
    metric: str
    expected: float
    actual: float
    tolerance: float

    @property
    def delta(self) -> float:
        return self.actual - self.expected

    @property
    def within_tolerance(self) -> bool:
        # A delta of exactly the tolerance passes. Comparing with `<=` alone is
        # not enough: 0.80 + 0.02 is 0.8200000000000001 in binary floating point,
        # which would fail a reproduction that is in fact exactly on the line.
        gap = abs(self.delta)
        return gap <= self.tolerance or math.isclose(gap, self.tolerance, rel_tol=1e-9)


@dataclass(frozen=True, slots=True)
class DiffReport:
    deltas: list[MetricDelta]
    missing_models: list[str]
    extra_models: list[str]

    @property
    def failures(self) -> list[MetricDelta]:
        return [d for d in self.deltas if not d.within_tolerance]

    @property
    def matches(self) -> bool:
        """A reproduction matches when nothing is missing and nothing is out of band.

        Extra models are not a failure: evaluating a model the release did not
        cover is a legitimate thing to do with the harness.
        """
        return not self.failures and not self.missing_models

    def render(self) -> str:
        lines: list[str] = []

        for model in self.missing_models:
            lines.append(f"missing  {model}: in the reference, absent from yours")
        for model in self.extra_models:
            lines.append(f"extra    {model}: in yours, absent from the reference")

        for delta in self.failures:
            lines.append(
                f"OUT      {delta.model} {delta.metric}: "
                f"{delta.actual:.4g} vs {delta.expected:.4g} "
                f"(delta {delta.delta:+.4g}, tolerance +/-{delta.tolerance:g})"
            )

        if self.matches:
            checked = len({d.model for d in self.deltas})
            lines.append(f"match    {checked} models within tolerance")

        return "\n".join(lines)


def _metric(row: ResultRow, name: str) -> float:
    return float(getattr(row, name))


def diff_summaries(
    actual: Summary,
    reference: Summary,
    tolerances: dict[str, float] | None = None,
) -> DiffReport:
    """Compare two summaries model by model, metric by metric."""
    limits = {**DEFAULT_TOLERANCES, **(tolerances or {})}

    actual_models = {row.model for row in actual.rows}
    reference_models = {row.model for row in reference.rows}

    deltas: list[MetricDelta] = []
    for model in sorted(actual_models & reference_models):
        mine = actual.row(model)
        theirs = reference.row(model)
        assert mine is not None and theirs is not None
        for metric in COMPARED_METRICS:
            deltas.append(
                MetricDelta(
                    model=model,
                    metric=metric,
                    expected=_metric(theirs, metric),
                    actual=_metric(mine, metric),
                    tolerance=limits[metric],
                )
            )

    return DiffReport(
        deltas=deltas,
        missing_models=sorted(reference_models - actual_models),
        extra_models=sorted(actual_models - reference_models),
    )
