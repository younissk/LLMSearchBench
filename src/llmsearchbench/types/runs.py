"""The answer side: what a model did on one task."""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types.base import BenchModel
from llmsearchbench.types.enums import Verdict


class RunRecord(BenchModel):
    """One (model, task) outcome — a single line of `raw.jsonl`."""

    task_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    answer: str
    citations: list[str]
    verdict: Verdict
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    latency_s: float = Field(ge=0)
    search_calls: int = Field(ge=0)
    #: Atomic claims the judge found unsupported, over total atomic claims.
    #: Both default to zero for runs made before per-claim support existed.
    unsupported_claims: int = Field(default=0, ge=0)
    total_claims: int = Field(default=0, ge=0)

    @property
    def is_judged(self) -> bool:
        return self.verdict is not Verdict.UNJUDGEABLE
