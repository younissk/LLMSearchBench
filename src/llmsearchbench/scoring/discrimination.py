"""Scoring the search-result-discrimination task.

Almost all of it is arithmetic. The ranking measures, the evidence measures and
the abstention measures are functions of a parsed reply and labels a person
wrote — no model is consulted, so nothing here can drift when a judge changes
its mind.

Only groundedness needs judgement, and that lives in `scoring.judging`, is
restricted to answers a model actually gave, and is reported separately.
"""

from __future__ import annotations

import collections
import json
import math
import re
from collections.abc import Sequence

from pydantic import Field

from llmsearchbench.scoring.tooluse import answer_matches
from llmsearchbench.types import BenchModel
from llmsearchbench.types.discrimination import Category, DiscriminationTask, NoiseTier
from llmsearchbench.types.judging import DiscriminationOutput, ParseProblem

#: Where nDCG is cut. Ten is the convention in retrieval evaluation, and the
#: twenty-candidate tier is the only one where it bites.
DEFAULT_K = 10

#: The first JSON object in a reply. Models wrap their answer in prose or a
#: fenced block often enough that refusing those would measure obedience.
JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_output(
    text: str, candidate_ids: Sequence[str]
) -> tuple[DiscriminationOutput, list[ParseProblem]]:
    """Read a model's reply into the shape the scorer needs.

    Lenient on purpose: this task measures whether a model can tell relevant
    results from noise, not whether it can follow a formatting instruction.
    Everything that had to be repaired is recorded, so the leniency is visible
    rather than free.
    """
    problems: list[ParseProblem] = []
    match = JSON_BLOCK.search(text)
    if match is None:
        return DiscriminationOutput(), [ParseProblem(kind="no-json", detail=text[:120])]

    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError as error:
        return DiscriminationOutput(), [ParseProblem(kind="bad-json", detail=error.msg)]

    if not isinstance(raw, dict):
        return DiscriminationOutput(), [
            ParseProblem(
                kind="bad-json", detail=f"expected an object, got {type(raw).__name__}"
            )
        ]

    known = set(candidate_ids)

    def ids(field: str, *, required: bool) -> list[str]:
        value = raw.get(field)
        if value is None:
            # `ranking` is optional: a model that only names the candidates it
            # would cite has still answered, and scoring falls back to that
            # order. A missing `relevant` is a real gap.
            if required:
                problems.append(ParseProblem(kind="missing-field", detail=field))
            return []
        if not isinstance(value, list):
            problems.append(ParseProblem(kind="missing-field", detail=f"{field} is not a list"))
            return []

        cleaned: list[str] = []
        for entry in value:
            # `[3]`, `3` and `"3"` all mean candidate 3.
            candidate = str(entry).strip().strip("[]").strip()
            if candidate not in known:
                problems.append(
                    ParseProblem(kind="unknown-candidate", detail=f"{field}: {candidate}")
                )
                continue
            if candidate in cleaned:
                problems.append(ParseProblem(kind="duplicate", detail=f"{field}: {candidate}"))
                continue
            cleaned.append(candidate)
        return cleaned

    answer = raw.get("answer")
    if answer is None:
        problems.append(ParseProblem(kind="missing-field", detail="answer"))

    return (
        DiscriminationOutput(
            ranking=ids("ranking", required=False),
            relevant=ids("relevant", required=True),
            answer=str(answer or ""),
        ),
        problems,
    )


def dcg(grades: Sequence[int], k: int) -> float:
    """Discounted cumulative gain, with the exponential gain of TREC practice.

    `2**g - 1` is what makes a perfect passage worth more than four merely
    related ones, which is the whole point of a graded scale.
    """
    total: float = sum(
        (2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades[:k])
    )
    return total


def ndcg(task: DiscriminationTask, ranking: Sequence[str], k: int = DEFAULT_K) -> float:
    """How well the model ordered the candidates, against the best possible order.

    Candidates the model left out rank below the ones it listed, in their
    original order: omitting a passage is a statement that it does not belong
    near the top, and dropping it from the calculation entirely would reward
    short answers.
    """
    listed = [cid for cid in ranking if cid in task.relevance]
    rest = [c.id for c in task.candidates if c.id not in set(listed)]
    order = listed + rest

    ideal = sorted(task.relevance.values(), reverse=True)
    best = dcg(ideal, k)
    if best == 0:
        # Nothing relevant to rank: every order is as good as every other, and
        # a zero here would punish the no_answer items for being no_answer.
        return 1.0
    return dcg([task.relevance[cid] for cid in order], k) / best


class ItemScore(BenchModel):
    """One model's result on one candidate set."""

    task_id: str
    category: Category
    noise_tier: NoiseTier

    #: None on a no-answer item: there is nothing to rank, so every order is
    #: as good as every other and a 1.0 there would be a free mark.
    ndcg: float | None = Field(default=None, ge=0, le=1)
    #: None on a no-answer item: with no supporting candidate, precision has no
    #: denominator worth having and recall has none at all. Scoring them zero
    #: was dragging every model's headline number down for getting the item
    #: right.
    precision: float | None = Field(default=None, ge=0, le=1)
    recall: float | None = Field(default=None, ge=0, le=1)
    f1: float | None = Field(default=None, ge=0, le=1)
    #: Share of the candidates it cited that were graded 0. Defined everywhere,
    #: and on a no-answer item it is the whole story.
    noise_picked: float = Field(ge=0, le=1)

    abstained: bool
    #: True when abstaining was the right move, False when it was not, None on
    #: items where the question does not arise.
    abstention_correct: bool | None = None

    #: None where the source carries no gold answer — the whole web category.
    answer_correct: bool | None = None
    parse_problems: list[ParseProblem] = Field(default_factory=list)

    @property
    def parsed(self) -> bool:
        return not any(p.kind in {"no-json", "bad-json"} for p in self.parse_problems)


def score_item(
    task: DiscriminationTask,
    output: DiscriminationOutput,
    problems: Sequence[ParseProblem] = (),
) -> ItemScore:
    """Everything arithmetic that can be said about one attempt."""
    chosen = set(output.relevant)
    supporting = set(task.supporting_ids)
    hit = chosen & supporting

    # An item with nothing relevant cannot be ranked and cannot be recalled.
    # Abstention accuracy is what measures it; the ranking and evidence columns
    # stay empty rather than being filled with a number that means nothing.
    answerable = bool(supporting)
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    if answerable:
        precision = len(hit) / len(chosen) if chosen else 0.0
        recall = len(hit) / len(supporting)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    noise = {cid for cid in chosen if task.relevance.get(cid, 0) == 0}

    answer_correct: bool | None = None
    if task.gold_answer:
        answer_correct = answer_matches(output.answer, task.gold_answer)

    return ItemScore(
        task_id=task.id,
        category=task.category,
        noise_tier=task.noise_tier,
        ndcg=ndcg(task, output.ranking or output.relevant) if answerable else None,
        precision=precision,
        recall=recall,
        f1=f1,
        noise_picked=len(noise) / len(chosen) if chosen else 0.0,
        abstained=output.abstained,
        abstention_correct=output.abstained == (not task.supporting_ids),
        answer_correct=answer_correct,
        parse_problems=list(problems),
    )


class Slice(BenchModel):
    """Averages over a group of items — a category, a tier, or everything.

    Averaged over the items where each measure is defined, which is not the
    same set for every column: a no-answer item counts toward abstention and
    noise-picked, and toward nothing else.
    """

    name: str
    items: int = Field(ge=0)
    #: How many of `items` could be ranked at all.
    rankable: int = Field(default=0, ge=0)
    ndcg: float | None = Field(default=None, ge=0, le=1)
    precision: float | None = Field(default=None, ge=0, le=1)
    recall: float | None = Field(default=None, ge=0, le=1)
    f1: float | None = Field(default=None, ge=0, le=1)
    noise_picked: float = Field(ge=0, le=1)
    #: Share of items where abstaining, or not, was the right call.
    abstention_accuracy: float = Field(ge=0, le=1)
    #: None when no item in the slice carries a gold answer.
    answer_accuracy: float | None = None


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def defined(values: Sequence[float | None]) -> float | None:
    """Average the items where the measure applies, or None when none do."""
    present = [value for value in values if value is not None]
    return mean(present) if present else None


def summarise(name: str, scores: Sequence[ItemScore]) -> Slice:
    answered = [s.answer_correct for s in scores if s.answer_correct is not None]
    return Slice(
        name=name,
        items=len(scores),
        rankable=sum(1 for s in scores if s.ndcg is not None),
        ndcg=defined([s.ndcg for s in scores]),
        precision=defined([s.precision for s in scores]),
        recall=defined([s.recall for s in scores]),
        f1=defined([s.f1 for s in scores]),
        noise_picked=mean([s.noise_picked for s in scores]),
        abstention_accuracy=mean([float(bool(s.abstention_correct)) for s in scores]),
        answer_accuracy=mean([float(a) for a in answered]) if answered else None,
    )


class DiscriminationScore(BenchModel):
    """One model's published result on the whole task."""

    model: str
    overall: Slice
    by_category: list[Slice] = Field(default_factory=list)
    by_tier: list[Slice] = Field(default_factory=list)
    #: Items whose reply could not be parsed at all. Not scored as zero — an
    #: unreadable reply is a missing measurement, the way a failed request is.
    unparsed: int = Field(default=0, ge=0)
    parse_problems: dict[str, int] = Field(default_factory=dict)

    #: Groundedness, when a judge has run. None when it has not.
    grounded_rate: float | None = None
    #: Verdicts thrown away because the judge's quote was not in the candidate
    #: it named. Published, because it says how far the judge can be trusted.
    discarded_verdicts: int = Field(default=0, ge=0)


def score(model: str, scores: Sequence[ItemScore]) -> DiscriminationScore:
    """Collapse per-item scores into one model's result.

    Unparseable replies are counted and dropped rather than scored as zero:
    a reply nobody could read is a measurement that did not happen, and the
    first task already learned what counting those as decisions does to a
    leaderboard.
    """
    usable = [s for s in scores if s.parsed]
    problems: collections.Counter[str] = collections.Counter(
        problem.kind for s in scores for problem in s.parse_problems
    )

    return DiscriminationScore(
        model=model,
        overall=summarise("overall", usable),
        by_category=[
            summarise(str(category), [s for s in usable if s.category is category])
            for category in Category
            if any(s.category is category for s in usable)
        ],
        by_tier=[
            summarise(str(tier), [s for s in usable if s.noise_tier is tier])
            for tier in NoiseTier
            if any(s.noise_tier is tier for s in usable)
        ],
        unparsed=len(scores) - len(usable),
        parse_problems=dict(problems),
    )
