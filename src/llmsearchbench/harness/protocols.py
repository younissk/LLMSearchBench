"""The seams a model, a search backend, and a judge plug into.

Written as protocols rather than base classes so an implementation owes us
nothing but a matching signature - and so the run loop can be driven by fakes
in tests without a network.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pydantic import Field

from llmsearchbench.harness.config import HarnessConfig
from llmsearchbench.types import BenchModel, Task, Verdict


class Document(BenchModel):
    """One retrieved document, as the search backend returned it."""

    url: str
    title: str
    text: str


class ModelAnswer(BenchModel):
    """What an adapter gives back for one task.

    Validated on construction because adapters are the seam where a third-party
    implementation can hand us something impossible - a negative token count
    would sail straight into a published cost.
    """

    answer: str
    citations: list[str]
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    latency_s: float = Field(ge=0)
    search_calls: int = Field(ge=0)


class Judgement(BenchModel):
    """The judge\'s ruling on one answer, with per-claim support."""

    verdict: Verdict
    unsupported_claims: int = Field(default=0, ge=0)
    total_claims: int = Field(default=0, ge=0)


class SearchBackend(Protocol):
    """Every model in a release gets the same backend, or the run is not comparable."""

    def search(self, query: str, top_k: int) -> Sequence[Document]: ...


class ModelAdapter(Protocol):
    def answer(
        self,
        task: Task,
        backend: SearchBackend,
        config: HarnessConfig,
    ) -> ModelAnswer: ...


class Judge(Protocol):
    def judge(
        self,
        task: Task,
        answer: ModelAnswer,
        retrieved: Sequence[Document],
    ) -> Judgement: ...
