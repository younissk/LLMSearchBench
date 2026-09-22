"""Running a model against a task set.

* `config` - the knobs held fixed across a release
* `protocols` - the seams a model, backend, and judge plug into
* `loop` - the run loop itself
* `adapters` - wiring an id to an implementation
* `fakes` - implementations that need no network
"""

from llmsearchbench.harness.adapters import NotConfiguredError, build_adapter, build_backend
from llmsearchbench.harness.config import HarnessConfig
from llmsearchbench.harness.fakes import EchoAdapter, StaticBackend
from llmsearchbench.harness.loop import RecordingBackend, run_task, run_tasks
from llmsearchbench.harness.protocols import (
    Document,
    Judge,
    Judgement,
    ModelAdapter,
    ModelAnswer,
    SearchBackend,
)

__all__ = [
    "Document",
    "EchoAdapter",
    "HarnessConfig",
    "Judge",
    "Judgement",
    "ModelAdapter",
    "ModelAnswer",
    "NotConfiguredError",
    "RecordingBackend",
    "SearchBackend",
    "StaticBackend",
    "build_adapter",
    "build_backend",
    "run_task",
    "run_tasks",
]
