"""One page's worth of evidence about a single task item.

The leaderboard says how often a model was right. These records say what it
actually did on one prompt, which is the only way to argue with a label: an
item every model "fails" is often an item this benchmark got wrong, and that
cannot be settled from a percentage.

Written per item rather than as one big file so a page carries its own data —
360 items times 34 models is not something to ship to a reader who opened one
of them.
"""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types.base import SiteModel
from llmsearchbench.types.enums import ToolProtocol


class ExampleModelResult(SiteModel):
    """What one model did with one item."""

    model: str = Field(min_length=1)
    label: str = Field(min_length=1)
    tool_protocol: ToolProtocol = ToolProtocol.NATIVE

    #: Did it reach for the search tool?
    searched: bool
    #: Was reaching, or not reaching, the right call?
    correct: bool
    #: The query it searched for, where it searched. Empty otherwise.
    query: str = ""
    #: What was wrong with the call, where anything was.
    call_problem: str = ""
    #: The beginning of the answer, for reading rather than scoring.
    answer_excerpt: str = ""


class ExampleReport(SiteModel):
    """One task item, and every model's attempt at it."""

    id: str = Field(min_length=1)
    bucket: str = Field(min_length=1)
    subcategory: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_id: str = ""
    adversarial: bool = False

    prompt: str = Field(min_length=1)
    #: Empty for `no_tool`, which is open-ended.
    gold_answer: list[str] = Field(default_factory=list)
    #: Why the item sits in its bucket, so a disputed label can be argued about.
    rationale: str = ""
    expects_search: bool

    results: list[ExampleModelResult] = Field(default_factory=list)

    @property
    def correct_count(self) -> int:
        return sum(1 for result in self.results if result.correct)
