"""Scoring the search-result-discrimination task.

One question: given a question and a pile of search results, most of which do
not answer it, did the model produce the right answer?

That is the whole measurement. Not how it ordered the results, not which ones
it would have cited — those are separate abilities, and measuring them in the
same run would mean reporting several things at once and being able to say
nothing clean about any of them.

Two ways to be right, counted apart:

* the results answer the question, and the model gave that answer;
* the results do not answer it, and the model said so instead of inventing one.

No model is consulted anywhere here. Both checks are string work against labels
a person wrote.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import Field

from llmsearchbench.harness.discrimination import NO_ANSWER_TOKEN
from llmsearchbench.taskgen.filters import fold
from llmsearchbench.types import BenchModel
from llmsearchbench.types.discrimination import Category, DiscriminationTask, NoiseTier

#: Phrasings that mean "the results do not answer this", for a model that did
#: not use the token it was given. Kept short and literal: anything looser
#: starts reading a hedged wrong answer as an abstention.
REFUSALS = (
    NO_ANSWER_TOKEN.lower(),
    "do not contain the answer",
    "does not contain the answer",
    "do not answer",
    "does not answer",
    "not enough information",
    "insufficient information",
    "cannot be answered",
    "cannot answer",
)


#: Words a gold answer may open with that carry no information. HotpotQA
#: writes its answers as sentence fragments — "at Westlake Recording Studios in
#: Los Angeles" — and a model that answers "Westlake Recording Studios in Los
#: Angeles" has answered it.
LEADING = ("at ", "in ", "on ", "the ", "a ", "an ", "to ", "of ", "by ")


def normalise(text: str) -> str:
    """Compare on the words, not the punctuation.

    Two real misses made this necessary: a gold answer of `"Woody" Allen`
    against a reply of `Woody Allen`, and one of `at Westlake Recording
    Studios in Los Angeles` against the same phrase without the `at`. Both
    replies were right and both were scored wrong.
    """
    folded = re.sub(r"[^\w\s]", " ", fold(text))
    return re.sub(r"\s+", " ", folded).strip()


def answer_matches(answer: str, gold: Sequence[str]) -> bool:
    """Does the reply contain any accepted answer?

    Containment rather than equality, and deliberately lenient: this task is
    about reading the results, not about reciting a string. Strict matching
    would measure formatting and call it comprehension.
    """
    reply = normalise(answer)
    if not reply:
        return False

    for alias in gold:
        wanted = normalise(alias)
        for prefix in LEADING:
            if wanted.startswith(prefix):
                wanted = wanted[len(prefix) :]
                break
        if wanted and wanted in reply:
            return True
    return False


def refused(answer: str) -> bool:
    """Did the model say the results do not answer the question?

    The token it was asked for counts, and so do a few plain phrasings — a
    model that says "the results do not answer this" has made the right call
    and should not be failed for wording.
    """
    folded = fold(answer)
    return bool(folded) and any(phrase in folded for phrase in REFUSALS)


class ItemScore(BenchModel):
    """Whether one model got one item right."""

    task_id: str
    category: Category
    noise_tier: NoiseTier

    #: True when none of the results answer the question.
    unanswerable: bool
    #: What the model did: gave an answer, or said the results have none.
    refused: bool
    #: The only thing this task scores.
    correct: bool
    #: The answer as given, kept for reading the run afterwards.
    answer: str = ""


def score_item(task: DiscriminationTask, answer: str) -> ItemScore:
    """Right or wrong, and nothing else.

    Where the results carry the answer, being right means giving it. Where they
    do not, being right means saying so — an answer there is wrong even when it
    is true in the world, because it did not come from the results.
    """
    said_no = refused(answer)
    unanswerable = not task.supporting_ids
    correct = (
        said_no if unanswerable else (not said_no and answer_matches(answer, task.gold_answer))
    )

    return ItemScore(
        task_id=task.id,
        category=task.category,
        noise_tier=task.noise_tier,
        unanswerable=unanswerable,
        refused=said_no,
        correct=correct,
        answer=answer[:300],
    )


class Slice(BenchModel):
    """One group of items — a category, a noise tier, or everything."""

    name: str
    items: int = Field(ge=0)
    correct: int = Field(ge=0)

    @property
    def accuracy(self) -> float:
        return self.correct / self.items if self.items else 0.0


def summarise(name: str, scores: Sequence[ItemScore]) -> Slice:
    return Slice(name=name, items=len(scores), correct=sum(1 for s in scores if s.correct))


class DiscriminationScore(BenchModel):
    """One model\'s result on the task."""

    model: str
    overall: Slice
    by_category: list[Slice] = Field(default_factory=list)
    by_tier: list[Slice] = Field(default_factory=list)

    #: Results carried the answer; the model said they did not. Too cautious.
    wrongly_refused: int = Field(default=0, ge=0)
    #: Results carried no answer; the model produced one anyway. Too credulous.
    fabricated: int = Field(default=0, ge=0)
    #: Items that never came back. Not scored as wrong.
    failed: int = Field(default=0, ge=0)


def score(model: str, scores: Sequence[ItemScore], *, failed: int = 0) -> DiscriminationScore:
    """Collapse per-item results into one model\'s number."""
    return DiscriminationScore(
        model=model,
        overall=summarise("overall", scores),
        by_category=[
            summarise(str(category), [s for s in scores if s.category is category])
            for category in Category
            if any(s.category is category for s in scores)
        ],
        by_tier=[
            summarise(str(tier), [s for s in scores if s.noise_tier is tier])
            for tier in NoiseTier
            if any(s.noise_tier is tier for s in scores)
        ],
        wrongly_refused=sum(1 for s in scores if not s.unanswerable and s.refused),
        fabricated=sum(1 for s in scores if s.unanswerable and not s.refused),
        failed=failed,
    )
