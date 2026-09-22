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

    #: End the episode the moment the model reaches for the tool, without
    #: running the search.
    #:
    #: The decision is made before any result comes back, so for measuring
    #: *whether* to search, executing the search adds nothing. It does add a
    #: second round trip, a search subscription, and — when results are empty —
    #: a retry loop that inflates the call count.
    #:
    #: What it gives up: multi-call behaviour. Duplicate queries, over-budget
    #: looping, and recovery from a bad call all need the episode to continue,
    #: and answer accuracy needs something retrieved.
    stop_at_first_call: bool = False
