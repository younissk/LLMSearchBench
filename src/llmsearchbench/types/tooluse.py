"""Records for the tool-use-correctness task.

This task asks a narrower question than the QA benchmark: given a prompt and a
search tool, does the model decide correctly whether to reach for it, and when
it does reach, does it call the tool properly?

Every item therefore carries an expectation rather than only a gold answer. The
three buckets differ in *why* a search is or is not warranted, and they fail in
different ways — see `Bucket`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from llmsearchbench.types.base import BenchModel
from llmsearchbench.types.enums import ToolProtocol


class Bucket(StrEnum):
    """Why a search is, or is not, the right move.

    The two no-search buckets are kept apart on purpose. Searching a
    `MEMORY` item is a confidence failure: the model knows the answer and did
    not trust itself. Searching a `NO_TOOL` item is a reflex failure: there was
    never a fact to look up. A single "over-search rate" would hide that.
    """

    #: A stable fact the model should already hold. Searching is wasted cost.
    MEMORY = "memory"
    #: Beyond the model's parametric knowledge. Answering without searching is
    #: a guess, however fluent.
    SEARCH = "search"
    #: Not a lookup at all — chat, arithmetic, creative work, text handed over
    #: in the prompt. There is nothing to retrieve.
    NO_TOOL = "no_tool"


class ToolUseTask(BenchModel):
    """One prompt, with what the model is expected to do about the search tool."""

    id: str = Field(min_length=1)
    bucket: Bucket
    prompt: str = Field(min_length=1)

    #: Accepted answers, for the buckets where correctness is checkable. Empty
    #: for `NO_TOOL`, where the task is open-ended and only the tool decision
    #: is scored.
    gold_answer: list[str] = Field(default_factory=list)

    #: Where the item came from: a dataset key, or the generator that wrote it.
    source: str = Field(min_length=1)
    #: The upstream identifier, when there is one.
    source_id: str | None = None
    #: Finer grain within a bucket: the sub-dataset, or the generated category.
    subcategory: str = Field(min_length=1)

    #: Worded to tempt a search that is not needed. Reported separately, since
    #: a model can score well overall and still fail every trap.
    adversarial: bool = False

    #: Why this item belongs in its bucket. Kept so a disputed label can be
    #: argued about without re-deriving the reasoning.
    rationale: str = ""

    @property
    def expects_search(self) -> bool:
        return self.bucket is Bucket.SEARCH

    @model_validator(mode="after")
    def _gold_answer_matches_bucket(self) -> Self:
        if self.bucket is Bucket.NO_TOOL and self.gold_answer:
            raise ValueError("no_tool items are open-ended and carry no gold answer")
        if self.bucket is not Bucket.NO_TOOL and not self.gold_answer:
            raise ValueError(f"{self.bucket} items need at least one gold answer")
        return self


class ToolCall(BenchModel):
    """One search call a model made, as the harness observed it."""

    #: The tool name the model asked for. Anything other than the search tool
    #: is a wrong-tool error.
    name: str
    #: Arguments as given. Kept raw so a malformed call is still recorded.
    arguments: dict[str, str] = Field(default_factory=dict)
    #: Set when the arguments did not satisfy the tool schema.
    schema_error: str | None = None
    #: True when the model wrote the call into its reply text instead of using
    #: the provider's tool-calling field. The decision to search was still
    #: made, so it counts as a search — but the call itself is malformed.
    emitted_as_text: bool = False

    @property
    def query(self) -> str:
        return self.arguments.get("query", "")


class ToolUseAttempt(BenchModel):
    """What one model did with one item.

    Everything here is raw observation. The costs and averages are derived from
    these fields at scoring time rather than stored, so a price correction does
    not require re-running anything.
    """

    task_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    answer: str = ""
    calls: list[ToolCall] = Field(default_factory=list)

    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    #: Thinking/reasoning tokens, where the provider reports them separately.
    #: Billed as output, so they are *included* in `tokens_out`, not added to it.
    reasoning_tokens: int = Field(default=0, ge=0)
    #: Input tokens served from the provider's cache, where reported.
    cached_tokens: int = Field(default=0, ge=0)

    latency_s: float = Field(default=0.0, ge=0)
    #: The provider's stop reason, kept for debugging odd runs.
    stop_reason: str = ""
    #: Set when the item failed outright; the attempt is recorded either way.
    error: str = ""

    #: How the tool was offered for this item. Old files predate the field and
    #: load as `native`, which is what they were.
    tool_protocol: ToolProtocol = ToolProtocol.NATIVE

    @property
    def searched(self) -> bool:
        return bool(self.calls)

    @property
    def failed(self) -> bool:
        return bool(self.error)

    @property
    def answer_chars(self) -> int:
        return len(self.answer)
