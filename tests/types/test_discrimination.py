"""The invariants a discrimination item has to satisfy.

These are the rules that make the task scoreable: every candidate labelled,
the supporting set derived from the labels rather than stated separately, and
a no-answer item genuinely having no answer in it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llmsearchbench.types.discrimination import (
    Candidate,
    Category,
    DiscriminationTask,
    LabelSource,
    NoiseTier,
)


def item(**overrides: object) -> DiscriminationTask:
    fields: dict[str, object] = {
        "id": "srd-web-test-1",
        "category": Category.WEB,
        "question": "who founded the company",
        "candidates": [
            Candidate(id="1", text="The company was founded by two engineers."),
            Candidate(id="2", text="An unrelated passage about fruit."),
        ],
        "relevance": {"1": 3, "2": 0},
        "supporting_ids": ["1"],
        "noise_tier": NoiseTier.EASY,
        "label_source": LabelSource.HUMAN,
        "source": "trec-dl-2019",
        "source_id": "19335",
        "subcategory": "dl19",
    }
    fields.update(overrides)
    return DiscriminationTask.model_validate(fields)


class TestLabels:
    def test_a_well_formed_item_is_accepted(self) -> None:
        assert item().relevant_count == 1

    def test_every_candidate_needs_a_label(self) -> None:
        with pytest.raises(ValidationError, match="exactly one relevance label"):
            item(
                candidates=[
                    Candidate(id="1", text="a relevant passage"),
                    Candidate(id="2", text="noise"),
                    Candidate(id="3", text="more noise"),
                ],
                relevance={"1": 3, "2": 0},
            )

    def test_a_label_without_a_candidate_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="exactly one relevance label"):
            item(relevance={"1": 3, "2": 0, "3": 1})

    def test_grades_stay_on_the_trec_scale(self) -> None:
        with pytest.raises(ValidationError, match="0 to 3"):
            item(relevance={"1": 4, "2": 0})

    def test_duplicate_candidate_ids_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            item(
                candidates=[
                    Candidate(id="1", text="first passage"),
                    Candidate(id="1", text="second passage"),
                ]
            )


class TestSupportingIds:
    def test_supporting_ids_must_match_the_grades(self) -> None:
        """Stated and derived cannot disagree: grade 2 and up is the definition."""
        with pytest.raises(ValidationError, match="exactly the candidates graded 2 or 3"):
            item(supporting_ids=["2"])

    def test_grade_one_is_not_support(self) -> None:
        """TREC's 'Related' means on topic and NOT answering, so it is not support."""
        task = item(relevance={"1": 1, "2": 0}, supporting_ids=[], category=Category.NO_ANSWER)
        assert task.supporting_ids == []
        assert task.relevant_count == 0


class TestNoAnswer:
    def test_a_no_answer_item_cannot_contain_the_answer(self) -> None:
        with pytest.raises(ValidationError, match="cannot have a relevant candidate"):
            item(category=Category.NO_ANSWER)

    def test_an_answerable_item_needs_something_to_find(self) -> None:
        with pytest.raises(ValidationError, match="need at least one relevant"):
            item(relevance={"1": 0, "2": 0}, supporting_ids=[])

    def test_has_answer_follows_the_category(self) -> None:
        assert item().has_answer
        assert not item(
            category=Category.NO_ANSWER, relevance={"1": 0, "2": 0}, supporting_ids=[]
        ).has_answer


class TestSerialisation:
    def test_the_task_file_stays_snake_case(self) -> None:
        """Task files are read by the harness, not the site; camelCase is for
        published results only."""
        dumped = item().model_dump(mode="json")
        assert "noise_tier" in dumped and "label_source" in dumped
        assert "supporting_ids" in dumped
