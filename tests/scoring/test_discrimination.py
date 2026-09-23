"""One question: was the answer right?

The task scores nothing else. Ranking the results and naming the evidence are
separate abilities, and measuring them in the same run meant reporting several
things at once and being able to say nothing clean about any of them.
"""

from __future__ import annotations

from llmsearchbench.harness.discrimination import NO_ANSWER_TOKEN
from llmsearchbench.scoring.discrimination import refused, score, score_item
from llmsearchbench.types.discrimination import (
    AnswerSource,
    Candidate,
    Category,
    DiscriminationTask,
    LabelSource,
    NoiseTier,
)


def task(**overrides: object) -> DiscriminationTask:
    fields: dict[str, object] = {
        "id": "srd-test-1",
        "category": Category.WIKIPEDIA,
        "question": "who replaced him",
        "candidates": [
            Candidate(id="1", text="Don Criqui was born in Buffalo, New York in 1940."),
            Candidate(id="2", text="Apples are a fruit produced by apple trees."),
            Candidate(id="3", text="Tony Roberts called Notre Dame football for decades."),
            Candidate(id="4", text="Eli Gold is a sportscaster who calls Alabama games."),
        ],
        "relevance": {"1": 3, "2": 0, "3": 3, "4": 0},
        "supporting_ids": ["1", "3"],
        "gold_answer": ["Notre Dame"],
        "answer_source": AnswerSource.DATASET,
        "noise_tier": NoiseTier.EASY,
        "label_source": LabelSource.DERIVED,
        "source": "hotpotqa",
        "source_id": "x",
        "subcategory": "bridge-hard",
    }
    fields.update(overrides)
    return DiscriminationTask.model_validate(fields)


def unanswerable() -> DiscriminationTask:
    return task(
        category=Category.NO_ANSWER,
        relevance={"1": 0, "2": 0, "3": 0, "4": 0},
        supporting_ids=[],
        gold_answer=[],
        answer_source=AnswerSource.NONE,
    )


class TestAnswerable:
    def test_the_right_answer_is_right(self) -> None:
        assert score_item(task(), "Notre Dame").correct

    def test_a_wrong_answer_is_wrong(self) -> None:
        assert not score_item(task(), "Alabama").correct

    def test_matching_is_lenient_about_wording(self) -> None:
        """The task is reading the results, not reciting a string."""
        assert score_item(task(), "the Notre Dame Fighting Irish").correct

    def test_refusing_when_the_answer_is_there_is_wrong(self) -> None:
        item = score_item(task(), NO_ANSWER_TOKEN)
        assert not item.correct
        assert item.refused


class TestUnanswerable:
    def test_saying_so_is_right(self) -> None:
        item = score_item(unanswerable(), NO_ANSWER_TOKEN)
        assert item.correct and item.refused

    def test_a_plain_phrasing_counts_too(self) -> None:
        assert score_item(unanswerable(), "The results do not answer this.").correct

    def test_answering_anyway_is_wrong_even_when_true(self) -> None:
        """A true answer that did not come from the results is still wrong.

        This is the failure the category exists to catch: a model reciting what
        it already knew while appearing to read.
        """
        item = score_item(unanswerable(), "Button quail lay about 90 to 120 eggs a year.")
        assert not item.correct
        assert not item.refused


class TestRefusalDetection:
    def test_the_token_is_recognised(self) -> None:
        assert refused(NO_ANSWER_TOKEN)

    def test_an_ordinary_answer_is_not_a_refusal(self) -> None:
        assert not refused("Notre Dame Fighting Irish football")

    def test_an_empty_answer_is_not_a_refusal(self) -> None:
        """Silence is not an abstention; the run loop records it as a failure."""
        assert not refused("   ")

    def test_a_hedged_answer_is_not_a_refusal(self) -> None:
        """Only a statement that the results lack the answer counts."""
        assert not refused("It is probably Notre Dame, though I am not certain.")


class TestAggregate:
    def test_the_two_ways_to_be_wrong_are_counted_apart(self) -> None:
        scores = [
            score_item(task(), NO_ANSWER_TOKEN),  # too cautious
            score_item(unanswerable(), "Some invented answer."),  # too credulous
            score_item(task(), "Notre Dame"),  # right
        ]
        result = score("m", scores, failed=2)
        assert result.overall.items == 3
        assert result.overall.correct == 1
        assert result.wrongly_refused == 1
        assert result.fabricated == 1
        # A failure never came back; it is not a wrong answer.
        assert result.failed == 2
        assert result.overall.accuracy == 1 / 3

    def test_slices_are_reported_per_category_and_tier(self) -> None:
        result = score(
            "m",
            [
                score_item(task(), "Notre Dame"),
                score_item(unanswerable(), NO_ANSWER_TOKEN),
            ],
        )
        assert {s.name for s in result.by_category} == {"wikipedia", "no_answer"}
        assert {s.name for s in result.by_tier} == {"easy"}


class TestPrompt:
    def test_the_prompt_asks_for_an_answer_and_nothing_else(self) -> None:
        from llmsearchbench.harness.discrimination import build_prompt

        prompt = build_prompt(task())
        assert NO_ANSWER_TOKEN in prompt
        assert "ranking" not in prompt.lower()
        assert "relevant" not in prompt.lower()

    def test_the_prompt_never_leaks_the_grades(self) -> None:
        from llmsearchbench.harness.discrimination import build_prompt

        item = task()
        prompt = build_prompt(item)
        for candidate_id, grade in item.relevance.items():
            assert f'"{candidate_id}": {grade}' not in prompt

    def test_an_empty_reply_is_a_failure_not_an_abstention(self) -> None:
        from llmsearchbench.harness.adapters import Turn
        from llmsearchbench.harness.discrimination import run_task

        class Silent:
            def complete(self, prompt: str, temperature: float = 0.0) -> Turn:
                return Turn(
                    answer="  ",
                    calls=[],
                    tokens_in=10,
                    tokens_out=4096,
                    latency_s=1.0,
                    stop_reason="length",
                )

        attempt = run_task(task(), "m", Silent())
        assert attempt.failed and "length" in attempt.error


class TestAnswerMatching:
    """Two real misses from the first run, pinned so they cannot come back."""

    def test_a_gold_answer_written_as_a_fragment(self) -> None:
        """HotpotQA writes answers as sentence fragments."""
        item = task(
            gold_answer=["at Westlake Recording Studios in Los Angeles"],
            answer_source=AnswerSource.DATASET,
        )
        assert score_item(item, "Westlake Recording Studios in Los Angeles").correct

    def test_punctuation_inside_a_gold_answer(self) -> None:
        item = task(gold_answer=['"Woody" Allen'], answer_source=AnswerSource.DATASET)
        assert score_item(item, "Woody Allen").correct

    def test_leniency_does_not_reach_a_different_answer(self) -> None:
        item = task(gold_answer=["Notre Dame"], answer_source=AnswerSource.DATASET)
        assert not score_item(item, "Alabama").correct

    def test_an_answer_inside_a_sentence_still_counts(self) -> None:
        assert score_item(task(), "The team was Notre Dame, per the results.").correct


class TestAnswerProvenance:
    """An item must say where its answer came from, and cannot claim one it
    does not have. The web answers are written by a model, not by a dataset,
    and a reader has to be able to tell."""

    def test_an_answer_needs_a_source(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="where it came from"):
            task(gold_answer=["Notre Dame"], answer_source=AnswerSource.NONE)

    def test_a_source_cannot_claim_an_answer_that_is_absent(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="claims an answer"):
            task(
                category=Category.NO_ANSWER,
                relevance={"1": 0, "2": 0, "3": 0, "4": 0},
                supporting_ids=[],
                gold_answer=[],
                answer_source=AnswerSource.ANNOTATED,
            )

    def test_an_annotated_answer_scores_like_any_other(self) -> None:
        """Provenance is recorded, not applied as a discount."""
        item = task(gold_answer=["High blood pressure"], answer_source=AnswerSource.ANNOTATED)
        assert score_item(item, "High blood pressure").correct
