"""What the documentation site publishes for a task.

One file per task, regenerated from the recorded attempts. Field names are
snake_case in Python and camelCase in the JSON, as everywhere the site reads.
"""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types.base import Fraction, SiteModel


class LeaderboardRow(SiteModel):
    """One model's published result for one task."""

    model: str = Field(min_length=1)
    #: Human-readable name from the catalogue, shown in the table.
    label: str = Field(min_length=1)
    provider: str = Field(min_length=1)

    #: How many items this model was actually scored on.
    items: int = Field(ge=0)
    #: False when the run did not cover the whole task set.
    complete: bool

    decision_accuracy: Fraction
    memory_accuracy: Fraction
    search_accuracy: Fraction
    no_tool_accuracy: Fraction
    adversarial_accuracy: Fraction
    well_formed_rate: Fraction

    over_search_memory: Fraction
    over_search_no_tool: Fraction
    under_search: Fraction

    cost_usd: float = Field(ge=0)
    is_free: bool = False
    tokens_out_mean: float = Field(ge=0)
    #: Share of output tokens spent thinking, where the provider reports it.
    reasoning_share: Fraction = 0.0
    latency_mean_s: float = Field(ge=0)


class TaskLeaderboard(SiteModel):
    """Every model that has been run against one task."""

    task: str = Field(min_length=1)
    title: str = Field(min_length=1)
    #: ISO date the file was generated.
    generated: str = Field(min_length=1)
    #: How many items the full task set has, so partial runs are obvious.
    task_items: int = Field(ge=0)
    rows: list[LeaderboardRow] = Field(default_factory=list)
