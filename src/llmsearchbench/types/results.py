"""What the documentation site reads.

Field names here are snake_case; the JSON they produce is camelCase, matching
`docs/src/data/types.ts`. `tests/test_site_contract.py` compares the aliases
below against that file and fails if the two drift.
"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field, model_validator

from llmsearchbench.types.base import SiteModel

#: A metric expressed as a share of tasks, not a percentage. 0.871, never 87.1.
Fraction = Annotated[float, Field(ge=0.0, le=1.0)]


class ResultRow(SiteModel):
    """One model's aggregate for one release — one row of the published table."""

    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    accuracy: Fraction
    citation_f1: Fraction
    hallucination_rate: Fraction
    #: Median seconds per task. Median, not mean: one stalled request should
    #: not move the published figure.
    latency_p50: float = Field(ge=0)
    #: USD per 1 000 tasks at list price, judge tokens excluded.
    #: The generated alias would be `costPer1K`; the site reads `costPer1k`.
    cost_per_1k: float = Field(ge=0, alias="costPer1k")
    #: Mean search tool calls per task. Context, not a score.
    search_calls: float = Field(ge=0)


class Summary(SiteModel):
    """`summary.json` — exactly what the documentation site renders."""

    version: str = Field(min_length=1)
    date: str = Field(min_length=1)
    task_count: int = Field(ge=0)
    placeholder: bool = False
    notes: str | None = None
    rows: list[ResultRow]

    @model_validator(mode="after")
    def _reject_duplicate_models(self) -> Self:
        """Two rows for one model would render as two indistinguishable lines."""
        seen = [row.model for row in self.rows]
        duplicates = sorted({name for name in seen if seen.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate model rows: {', '.join(duplicates)}")
        return self

    def row(self, model: str) -> ResultRow | None:
        return next((row for row in self.rows if row.model == model), None)
