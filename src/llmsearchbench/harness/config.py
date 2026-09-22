"""The knobs held fixed across a release."""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types import BenchModel


class HarnessConfig(BenchModel):
    """Fixed across every model in a release. Changing one is a MAJOR bump."""

    max_calls: int = Field(default=6, ge=1)
    top_k: int = Field(default=5, ge=1)
    temperature: float = Field(default=0.0, ge=0.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
