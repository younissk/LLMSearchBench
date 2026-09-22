"""Running a model against a task set.

* `config` — the knobs held fixed across a release
* `protocols` — the seams a model, backend, and judge plug into
* `loop` — the generic QA run loop
* `tooluse` — the run loop for the tool-use-correctness task
* `adapters` — talking to a model
* `search` — the search backends a model is given
* `fakes` — implementations that need no network
"""

from llmsearchbench.harness.adapters import (
    SEARCH_TOOL,
    AnthropicAdapter,
    NotConfiguredError,
    build_adapter,
    validate_search_arguments,
)
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
from llmsearchbench.harness.search import (
    BACKENDS,
    LIVE_BACKENDS,
    BackendNotConfiguredError,
    NullBackend,
    SearchError,
    build_backend,
)

__all__ = [
    "BACKENDS",
    "LIVE_BACKENDS",
    "SEARCH_TOOL",
    "AnthropicAdapter",
    "BackendNotConfiguredError",
    "Document",
    "EchoAdapter",
    "HarnessConfig",
    "Judge",
    "Judgement",
    "ModelAdapter",
    "ModelAnswer",
    "NotConfiguredError",
    "NullBackend",
    "RecordingBackend",
    "SearchBackend",
    "SearchError",
    "StaticBackend",
    "build_adapter",
    "build_backend",
    "run_task",
    "run_tasks",
    "validate_search_arguments",
]
