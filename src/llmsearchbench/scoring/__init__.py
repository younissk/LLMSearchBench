"""How a run becomes a number.

* `metrics` - the per-answer formulas
* `aggregate` - per-task records collapsed into one published row
* `compare` - a reproduction checked against a published release
"""

from llmsearchbench.scoring.aggregate import UNJUDGEABLE_LIMIT, aggregate, unjudgeable_share
from llmsearchbench.scoring.compare import (
    COMPARED_METRICS,
    DEFAULT_TOLERANCES,
    DiffReport,
    MetricDelta,
    diff_summaries,
)
from llmsearchbench.scoring.metrics import citation_f1, cost_per_1k, unsupported_claim_rate

__all__ = [
    "COMPARED_METRICS",
    "DEFAULT_TOLERANCES",
    "UNJUDGEABLE_LIMIT",
    "DiffReport",
    "MetricDelta",
    "aggregate",
    "citation_f1",
    "cost_per_1k",
    "diff_summaries",
    "unjudgeable_share",
    "unsupported_claim_rate",
]
