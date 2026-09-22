"""Per-answer metric definitions.

Every formula here is stated in prose on the documentation site under
Methodology -> Scoring. If you change one, change both, and bump MAJOR: a
scoring change voids every published number.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from llmsearchbench.types import RunRecord


def citation_f1(cited: Iterable[str], gold: Iterable[str]) -> float:
    """Harmonic mean of set precision and recall over cited URLs.

    An answer that cites nothing scores 0. A task with no gold sources (which
    the negative category allows) scores 1 when nothing is cited, since there
    was nothing to find.
    """
    cited_set = set(cited)
    gold_set = set(gold)

    if not gold_set:
        return 1.0 if not cited_set else 0.0
    if not cited_set:
        return 0.0

    hits = len(cited_set & gold_set)
    if hits == 0:
        return 0.0

    precision = hits / len(cited_set)
    recall = hits / len(gold_set)
    return 2 * precision * recall / (precision + recall)


def unsupported_claim_rate(record: RunRecord) -> float:
    """Fraction of a single answer\'s atomic claims that no retrieved source backs."""
    if record.total_claims <= 0:
        return 0.0
    return record.unsupported_claims / record.total_claims


def cost_per_1k(
    records: Sequence[RunRecord],
    *,
    price_in_per_mtok: float,
    price_out_per_mtok: float,
) -> float:
    """USD per 1 000 tasks at list price.

    Judge tokens are excluded on purpose - they are a property of the harness,
    not of the model under test.
    """
    if not records:
        return 0.0

    total = sum(
        record.tokens_in / 1_000_000 * price_in_per_mtok
        + record.tokens_out / 1_000_000 * price_out_per_mtok
        for record in records
    )
    return total / len(records) * 1000
