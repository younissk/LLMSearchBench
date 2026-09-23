"""Records for the search-result-discrimination task.

The retrieval step is over before this task begins. Every model sees the same
question and the same candidate results, in the same order, so nothing here
measures a retriever — only whether a model can tell which of those results
bear on the question.

Keeping the candidate set fixed is the whole design. A model that answers a
question correctly from memory tells you nothing about its reading of the
results, so the task asks for the evidence as well as the answer, and scores
the two separately.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from llmsearchbench.types.base import BenchModel


class Category(StrEnum):
    """Where the candidate results came from.

    Kept as a dimension rather than folded together: a model can be good at
    web snippets and poor at multi-paragraph Wikipedia, and an average over
    both would hide it.
    """

    #: Web passages with graded human relevance judgements (TREC Deep Learning).
    WEB = "web"
    #: Wikipedia paragraphs, two of which carry the answer (HotpotQA distractor).
    WIKIPEDIA = "wikipedia"
    #: Every candidate was judged non-relevant by a human. The right answer is
    #: that the results do not contain one.
    NO_ANSWER = "no_answer"


class NoiseTier(StrEnum):
    """How much there is to read. Reported separately so the fall-off with
    candidate count is visible rather than averaged away."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class LabelSource(StrEnum):
    """Who decided a candidate was relevant.

    A human judgement and a heuristic are not the same evidence, and a
    benchmark that prints one number over both is lying about its own
    confidence.
    """

    #: A person judged this candidate against this question.
    HUMAN = "human"
    #: Derived from a dataset's own structure — supporting facts, gold
    #: paragraph titles — rather than a direct relevance judgement.
    DERIVED = "derived"


class AnswerSource(StrEnum):
    """Where an item's gold answer came from.

    A dataset's own answer and one a model wrote are not the same evidence, and
    an item says which it carries rather than leaving a reader to assume.
    """

    #: The source dataset shipped the answer. HotpotQA does.
    DATASET = "dataset"
    #: Written by an annotator model from passages a human graded relevant,
    #: with a verbatim quote checked against the passage. Weaker than a
    #: dataset's own answer, and never mixed into one number with it silently.
    ANNOTATED = "annotated"
    #: No answer, because the results do not contain one.
    NONE = "none"


class Candidate(BenchModel):
    """One search result put in front of the model."""

    #: Stable within an item, and what the model is asked to cite: `[1]`, `[2]`.
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    #: The id this passage has upstream, so a candidate can be traced back.
    source_id: str = ""
    #: Where the text came from, for a reader looking at one item.
    title: str = ""


class DiscriminationTask(BenchModel):
    """One question, one fixed candidate set, and the graded truth about it."""

    id: str = Field(min_length=1)
    category: Category
    question: str = Field(min_length=1)

    #: In the order the model sees them. Shuffled at build time with a fixed
    #: seed, so position carries no signal but the order is reproducible.
    candidates: list[Candidate] = Field(min_length=2)

    #: Candidate id -> graded relevance. TREC's scale throughout:
    #: 0 irrelevant, 1 related but not answering, 2 highly relevant,
    #: 3 perfectly relevant. Derived labels only ever use 0 and 3, because a
    #: dataset's supporting facts do not carry a grade.
    relevance: dict[str, int] = Field(min_length=2)

    #: The candidates a correct answer must rest on: relevance >= 2. Empty for
    #: `no_answer`, where there are none.
    supporting_ids: list[str] = Field(default_factory=list)

    #: Accepted answers, where there are any. Empty for `no_answer`, where the
    #: right response is that the results do not contain one.
    gold_answer: list[str] = Field(default_factory=list)
    answer_source: AnswerSource = AnswerSource.NONE

    noise_tier: NoiseTier
    label_source: LabelSource
    #: Dataset key this item was built from.
    source: str = Field(min_length=1)
    #: The upstream query or question id.
    source_id: str = Field(min_length=1)
    #: Finer grain within a category: the year, the question type.
    subcategory: str = Field(min_length=1)

    #: Set when this item shares its question with another, at a different
    #: noise tier or as a no-answer variant. Scoring never mixes an item with
    #: its variant, since they are not independent.
    variant_of: str = ""

    #: Why this item is what it claims to be, kept so a disputed label can be
    #: argued about without re-deriving the build.
    rationale: str = ""

    @property
    def relevant_count(self) -> int:
        return sum(1 for grade in self.relevance.values() if grade >= 2)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def has_answer(self) -> bool:
        return self.category is not Category.NO_ANSWER

    @model_validator(mode="after")
    def _answer_source_matches_the_answer(self) -> Self:
        if self.gold_answer and self.answer_source is AnswerSource.NONE:
            raise ValueError("an item with a gold answer must say where it came from")
        if not self.gold_answer and self.answer_source is not AnswerSource.NONE:
            raise ValueError(f"{self.answer_source} claims an answer this item does not have")
        return self

    @model_validator(mode="after")
    def _labels_cover_candidates(self) -> Self:
        ids = [candidate.id for candidate in self.candidates]
        if len(set(ids)) != len(ids):
            raise ValueError("candidate ids must be unique within an item")
        if set(self.relevance) != set(ids):
            raise ValueError("every candidate needs exactly one relevance label")
        if any(grade < 0 or grade > 3 for grade in self.relevance.values()):
            raise ValueError("relevance grades run 0 to 3")

        expected = sorted(cid for cid, grade in self.relevance.items() if grade >= 2)
        if sorted(self.supporting_ids) != expected:
            raise ValueError("supporting_ids must be exactly the candidates graded 2 or 3")

        if self.category is Category.NO_ANSWER and self.supporting_ids:
            raise ValueError("a no_answer item cannot have a relevant candidate")
        if self.category is not Category.NO_ANSWER and not self.supporting_ids:
            raise ValueError(f"{self.category} items need at least one relevant candidate")
        return self
