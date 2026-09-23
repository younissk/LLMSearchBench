"""Record types, one module per concern.

* `enums` — the closed vocabularies (`Category`, `Verdict`)
* `tasks` — the question side (`Task`)
* `runs` — the answer side (`RunRecord`)
* `results` — what the documentation site reads (`ResultRow`, `Summary`)
* `manifest` — what makes a published number checkable (`Manifest`)

All of them are Pydantic models: frozen, and `extra="forbid"`, so a typo'd key
in an artefact fails at load rather than silently dropping a metric.
"""

from llmsearchbench.types.base import BenchModel, Fraction, SiteModel
from llmsearchbench.types.enums import Category, Verdict
from llmsearchbench.types.leaderboard import (
    ItemMeta,
    LeaderboardRow,
    ModelItems,
    TaskItemMatrix,
    TaskLeaderboard,
)
from llmsearchbench.types.manifest import Manifest
from llmsearchbench.types.runs import RunRecord
from llmsearchbench.types.tasks import Task

__all__ = [
    "BenchModel",
    "Category",
    "Fraction",
    "ItemMeta",
    "LeaderboardRow",
    "Manifest",
    "ModelItems",
    "RunRecord",
    "SiteModel",
    "Task",
    "TaskItemMatrix",
    "TaskLeaderboard",
    "Verdict",
]
