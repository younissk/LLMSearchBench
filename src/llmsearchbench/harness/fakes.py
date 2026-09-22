"""Implementations that need no network.

These exist so the run loop can be exercised for real - in tests, and by hand
while developing - without an API key or a search subscription.
"""

from __future__ import annotations

from collections.abc import Sequence

from llmsearchbench.harness.config import HarnessConfig
from llmsearchbench.harness.protocols import Document, ModelAnswer, SearchBackend
from llmsearchbench.types import Task


class StaticBackend:
    """A fixed corpus, searched by substring."""

    def __init__(self, documents: Sequence[Document]) -> None:
        self._documents = list(documents)

    def search(self, query: str, top_k: int) -> Sequence[Document]:
        terms = [term for term in query.lower().split() if term]
        scored = [
            (sum(term in (doc.title + " " + doc.text).lower() for term in terms), doc)
            for doc in self._documents
        ]
        hits = [doc for score, doc in sorted(scored, key=lambda pair: -pair[0]) if score > 0]
        return hits[:top_k]


class EchoAdapter:
    """A model that never searches and answers with the question."""

    def answer(
        self,
        task: Task,
        backend: SearchBackend,  # noqa: ARG002 - the ModelAdapter protocol dictates this
        config: HarnessConfig,  # noqa: ARG002 - the ModelAdapter protocol dictates this
    ) -> ModelAnswer:
        return ModelAnswer(
            answer=task.question,
            citations=[],
            tokens_in=0,
            tokens_out=0,
            latency_s=0.0,
            search_calls=0,
        )
