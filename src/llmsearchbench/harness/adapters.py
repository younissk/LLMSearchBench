"""Wiring a model id or a backend name to an implementation.

Nothing here talks to a network yet. Add an implementation of the protocols in
`llmsearchbench.harness.protocols`, register it below, and the CLI picks it up.
"""

from __future__ import annotations

from llmsearchbench.harness.protocols import ModelAdapter, SearchBackend
from llmsearchbench.providers import get_model


class NotConfiguredError(RuntimeError):
    """Raised when a run is asked for a model or backend that has no adapter yet."""


def build_adapter(model_id: str) -> ModelAdapter:
    """Return the adapter for a model id.

    Deliberately fails loudly: a benchmark that silently substitutes a different
    model produces numbers nobody can place.
    """
    get_model(model_id)  # unknown ids fail here, with the catalogue in the message
    raise NotConfiguredError(
        f"no adapter is wired up for {model_id!r}. "
        "Implement the ModelAdapter protocol in "
        "src/llmsearchbench/harness/adapters.py and register it in build_adapter()."
    )


def build_backend(name: str) -> SearchBackend:
    raise NotConfiguredError(
        f"no search backend is wired up for {name!r}. "
        "Implement the SearchBackend protocol in "
        "src/llmsearchbench/harness/adapters.py and register it in build_backend()."
    )
