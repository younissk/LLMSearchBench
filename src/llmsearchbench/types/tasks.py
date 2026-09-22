"""The question side of the benchmark."""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types.base import BenchModel
from llmsearchbench.types.enums import Category


class Task(BenchModel):
    """One question, its gold answer, and the sources that support it."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    gold_answer: str
    #: The sources that actually support the answer. Empty for negative tasks,
    #: where the correct behaviour is to cite nothing and decline.
    gold_sources: list[str]
    category: Category
    #: For freshness tasks: the date before which a source is too old to count.
    freshness_cutoff: str | None = None

    @property
    def is_negative(self) -> bool:
        return self.category is Category.NEGATIVE
