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
