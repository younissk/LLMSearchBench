"""Putting a prompt to a model and recording what it did.

* `adapters` — talking to a model; the tool is offered, never executed
* `openrouter` — the OpenRouter route
* `tooluse` — the run loop
"""

from llmsearchbench.harness.adapters import (
    SEARCH_TOOL,
    AnthropicAdapter,
    NotConfiguredError,
    Turn,
    build_adapter,
    validate_search_arguments,
)
from llmsearchbench.harness.tooluse import completed_task_ids, run_task, run_tasks

__all__ = [
    "SEARCH_TOOL",
    "AnthropicAdapter",
    "NotConfiguredError",
    "Turn",
    "build_adapter",
    "completed_task_ids",
    "run_task",
    "run_tasks",
    "validate_search_arguments",
]
