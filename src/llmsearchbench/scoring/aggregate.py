"""Collapsing a model\'s per-task records into one published row."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median

from llmsearchbench.scoring.metrics import citation_f1, cost_per_1k, unsupported_claim_rate
from llmsearchbench.types import ResultRow, RunRecord, Verdict

#: A release with more than this share of unjudgeable answers is rejected and
#: the offending tasks rewritten.
UNJUDGEABLE_LIMIT = 0.02


def aggregate(
    model: str,
    provider: str,
    records: Sequence[RunRecord],
    gold_sources: dict[str, Sequence[str]],
    *,
    price_in_per_mtok: float,
    price_out_per_mtok: float,
) -> ResultRow:
    """Collapse one model\'s per-task records into a published table row.

    `unjudgeable` verdicts are dropped from the accuracy denominator and logged
    by the caller.
    """
    if not records:
        raise ValueError(f"no records for model {model!r}")

    judged = [record for record in records if record.is_judged]
    correct = sum(1 for record in judged if record.verdict is Verdict.CORRECT)
    accuracy = correct / len(judged) if judged else 0.0

    f1_scores = [citation_f1(r.citations, gold_sources.get(r.task_id, ())) for r in records]
    ucr_scores = [unsupported_claim_rate(r) for r in records]

    return ResultRow(
        model=model,
        provider=provider,
        accuracy=accuracy,
        citation_f1=sum(f1_scores) / len(f1_scores),
        hallucination_rate=sum(ucr_scores) / len(ucr_scores),
        latency_p50=median(record.latency_s for record in records),
        cost_per_1k=cost_per_1k(
            records,
            price_in_per_mtok=price_in_per_mtok,
            price_out_per_mtok=price_out_per_mtok,
        ),
        search_calls=sum(record.search_calls for record in records) / len(records),
    )


def unjudgeable_share(records: Sequence[RunRecord]) -> float:
    """Fraction of records the judge could not rule on."""
    if not records:
        return 0.0
    return sum(1 for record in records if not record.is_judged) / len(records)
