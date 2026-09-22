"""The record that makes a published number checkable."""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types.base import BenchModel


class Manifest(BenchModel):
    """The exact inputs that produced a release.

    A results directory without one is not publishable: without the model ids,
    the judge, and the harness commit, a number cannot be placed or rerun.
    """

    version: str = Field(min_length=1)
    date: str = Field(min_length=1)
    harness_commit: str = Field(min_length=1)
    #: Changing this is always a MAJOR bump, even with the task set untouched.
    judge_model: str = Field(min_length=1)
    #: Display label -> the exact id sent to the API.
    model_ids: dict[str, str] = Field(default_factory=dict)
    retrieval_backend: str = ""
    task_count: int = Field(default=0, ge=0)
