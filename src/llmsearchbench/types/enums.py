"""The closed vocabularies a record can use."""

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    """What a task is designed to stress. Shares proportions with the task set."""

    SINGLE_HOP = "single-hop"
    MULTI_HOP = "multi-hop"
    FRESHNESS = "freshness"
    NEGATIVE = "negative"


class Verdict(StrEnum):
    """The judge's ruling on one answer."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    #: The judge could not rule. Dropped from the accuracy denominator, and
    #: capped at 2% of a release before the release is rejected.
    UNJUDGEABLE = "unjudgeable"


class ToolProtocol(StrEnum):
    """How the search tool was put in front of the model.

    Results from the two are *not* strictly comparable: the prompted protocol
    adds instructions to every prompt and asks the model to imitate a tool call
    in prose, which is a different skill from emitting one. It exists for
    providers whose server has tool calling switched off, where the choice is
    a prompted number or no number at all.
    """

    #: The provider's own tool-calling API. The default, and what the
    #: leaderboard is about.
    NATIVE = "native"
    #: The tool is described in the prompt and the "call" is parsed out of the
    #: reply text.
    PROMPTED = "prompted"
