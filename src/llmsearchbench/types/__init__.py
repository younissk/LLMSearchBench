"""Record types, one module per concern.

* `enums` — the closed vocabularies (`Category`, `Verdict`)
* `tasks` — the question side (`Task`)
* `runs` — the answer side (`RunRecord`)
* `results` — what the documentation site reads (`ResultRow`, `Summary`)
* `manifest` — what makes a published number checkable (`Manifest`)

All of them are Pydantic models: frozen, and `extra="forbid"`, so a typo'd key
in an artefact fails at load rather than silently dropping a metric.
"""

from llmsearchbench.types.base import BenchModel, SiteModel
from llmsearchbench.types.enums import Category, Verdict
from llmsearchbench.types.manifest import Manifest
from llmsearchbench.types.results import Fraction, ResultRow, Summary
from llmsearchbench.types.runs import RunRecord
from llmsearchbench.types.tasks import Task

__all__ = [
    "BenchModel",
    "Category",
    "Fraction",
    "Manifest",
    "ResultRow",
    "RunRecord",
    "SiteModel",
    "Summary",
    "Task",
    "Verdict",
]
