"""What the documentation site publishes for a task.

One file per task, regenerated from the recorded attempts. Field names are
snake_case in Python and camelCase in the JSON, as everywhere the site reads.
"""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types.base import Fraction, SiteModel
from llmsearchbench.types.enums import ToolProtocol


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
    #: `prompted` marks a model whose provider has tool calling disabled: the
    #: tool was described in the prompt instead. Shown as a badge, because the
    #: number answers a slightly different question.
    tool_protocol: ToolProtocol = ToolProtocol.NATIVE
    #: Billions of parameters, measured from the published weights. Absent for
    #: a closed model and for one whose repo has not been checked — never
    #: estimated, since the whole point is deciding what to fine-tune.
    params_b: float | None = Field(default=None, gt=0)

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
    #: The part of `cost_usd` spent on searches that should not have happened.
    wasted_usd: float = Field(default=0.0, ge=0)
    #: Total spend divided by right decisions. Zero for an unpriced model.
    usd_per_correct_decision: float = Field(default=0.0, ge=0)
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


class ItemMeta(SiteModel):
    """One task item, as the charts need to see it."""

    id: str = Field(min_length=1)
    bucket: str = Field(min_length=1)
    subcategory: str = Field(min_length=1)
    source: str = Field(min_length=1)
    adversarial: bool = False


class ModelItems(SiteModel):
    """One model's per-item result, encoded one character per item.

    A string rather than an array of objects: 36 models x 360 items is a file
    the browser downloads, and the objects would be forty times the size for
    the same information.
    """

    model: str = Field(min_length=1)
    label: str = Field(min_length=1)
    tool_protocol: ToolProtocol = ToolProtocol.NATIVE

    #: In `items` order. `A` correct abstain, `S` correct search,
    #: `O` over-search, `U` under-search.
    decisions: str
    #: In `items` order. `.` no call, `+` well-formed call, `x` malformed call.
    calls: str


class TaskItemMatrix(SiteModel):
    """Every model's answer on every item, for the per-item charts.

    Only complete runs appear: a partial run would leave holes in a string
    whose whole point is that position means item.
    """

    task: str = Field(min_length=1)
    generated: str = Field(min_length=1)
    items: list[ItemMeta] = Field(default_factory=list)
    models: list[ModelItems] = Field(default_factory=list)
