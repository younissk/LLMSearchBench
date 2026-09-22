"""LLMSearchBench: a small, reproducible benchmark for how models use search.

The package is laid out by concern:

* `types` — the records, as Pydantic models
* `providers` — who serves which model, and at what price
* `datasets` — source data: the registry, the downloader, the credit it carries
* `taskgen` — building the task set from source data
* `scoring` — the three measurements, and what a run cost
* `harness` — putting a prompt to a model and recording what it did
* `storage` — artefacts on disk
* `ui` — the Rich consoles; the only package that knows about a terminal
* `cli` — the Typer app, one module per command group

Nothing below `ui` and `cli` touches a terminal, so the library can be driven
from a notebook or another program with no console attached.
"""

from llmsearchbench.types import LeaderboardRow, Manifest, RunRecord, Task, TaskLeaderboard

__version__ = "0.1.0"

__all__ = [
    "LeaderboardRow",
    "Manifest",
    "RunRecord",
    "Task",
    "TaskLeaderboard",
    "__version__",
]
