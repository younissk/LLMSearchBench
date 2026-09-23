"""Scoring one candidate set, and keeping the judge honest."""

from __future__ import annotations

import pytest

from llmsearchbench.scoring.discrimination import (
    ItemScore,
    ndcg,
    parse_output,
    score,
    score_item,
)
from llmsearchbench.scoring.judging import (
    build_prompt,
    grounded_rate,
    judge_run,
    parse_verdicts,
    verify,
)
from llmsearchbench.types.discrimination import (
    Candidate,
    Category,
    DiscriminationTask,
    LabelSource,
    NoiseTier,
)
from llmsearchbench.types.enums import Verdict
from llmsearchbench.types.judging import (
    DiscriminationOutput,
    GroundednessVerdict,
    JudgeKind,
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
        "noise_tier": NoiseTier.EASY,
        "label_source": LabelSource.DERIVED,
        "source": "hotpotqa",
        "source_id": "x",
        "subcategory": "bridge-hard",
    }
    fields.update(overrides)
    return DiscriminationTask.model_validate(fields)


class TestParsing:
    def test_a_clean_reply(self) -> None:
        output, problems = parse_output(
            '{"ranking": ["3", "1", "2", "4"], "relevant": ["1", "3"], "answer": "Notre Dame"}',
            ["1", "2", "3", "4"],
        )
        assert output.relevant == ["1", "3"]
        assert output.answer == "Notre Dame"
        assert problems == []

    def test_prose_around_the_json_is_tolerated(self) -> None:
        """This task measures reading, not obedience about formatting."""
        output, problems = parse_output(
            "Here is my answer:\n```json\n"
            '{"ranking": [3, 1], "relevant": [3], "answer": "x"}\n```',
            ["1", "2", "3"],
        )
        assert output.relevant == ["3"]
        assert output.ranking == ["3", "1"]
        assert problems == []

    def test_bracketed_ids_are_normalised(self) -> None:
        output, _ = parse_output('{"relevant": ["[2]"], "answer": "x"}', ["1", "2"])
        assert output.relevant == ["2"]

    def test_an_invented_candidate_is_recorded_and_dropped(self) -> None:
        output, problems = parse_output('{"relevant": ["9"], "answer": "x"}', ["1", "2"])
        assert output.relevant == []
        assert [p.kind for p in problems] == ["unknown-candidate"]

    def test_a_reply_with_no_json_is_a_parse_failure(self) -> None:
        output, problems = parse_output("I think result three is best.", ["1", "2", "3"])
        assert output.relevant == []
        assert problems[0].kind == "no-json"


class TestNdcg:
    def test_a_perfect_ordering_scores_one(self) -> None:
        assert ndcg(task(), ["1", "3", "2", "4"]) == pytest.approx(1.0)

    def test_the_worst_ordering_scores_least(self) -> None:
        best = ndcg(task(), ["1", "3", "2", "4"])
        worst = ndcg(task(), ["2", "4", "1", "3"])
        assert worst < best

    def test_omitted_candidates_fall_to_the_back(self) -> None:
        """Leaving a passage out says it does not belong at the top."""
        listed_only_noise = ndcg(task(), ["2"])
        assert listed_only_noise < ndcg(task(), ["1", "3"])

    def test_a_no_answer_item_cannot_be_failed_on_ranking(self) -> None:
        """With nothing relevant, every order is equally right."""
        none = task(
            category=Category.NO_ANSWER,
            relevance={"1": 0, "2": 0, "3": 0, "4": 0},
            supporting_ids=[],
            gold_answer=[],
        )
        assert ndcg(none, ["4", "2", "1", "3"]) == 1.0


class TestItemScore:
    def test_picking_both_supporting_candidates(self) -> None:
        result = score_item(
            task(), DiscriminationOutput(relevant=["1", "3"], answer="Notre Dame")
        )
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.noise_picked == 0.0
        assert result.answer_correct

    def test_picking_noise_costs_precision_not_recall(self) -> None:
        result = score_item(task(), DiscriminationOutput(relevant=["1", "3", "2"], answer="x"))
        assert result.recall == 1.0
        assert result.precision == pytest.approx(2 / 3)
        assert result.noise_picked == pytest.approx(1 / 3)

    def test_abstaining_on_an_answerable_item_is_wrong(self) -> None:
        result = score_item(task(), DiscriminationOutput(relevant=[], answer="I cannot tell"))
        assert result.abstained
        assert result.abstention_correct is False

    def test_abstaining_on_a_no_answer_item_is_right(self) -> None:
        none = task(
            category=Category.NO_ANSWER,
            relevance={"1": 0, "2": 0, "3": 0, "4": 0},
            supporting_ids=[],
            gold_answer=[],
        )
        result = score_item(
            none, DiscriminationOutput(relevant=[], answer="not in the results")
        )
        assert result.abstention_correct is True

    def test_an_item_without_a_gold_answer_is_not_scored_for_correctness(self) -> None:
        """TREC judged relevance, not answers; inventing one would be fiction."""
        web = task(category=Category.WEB, gold_answer=[], label_source=LabelSource.HUMAN)
        result = score_item(web, DiscriminationOutput(relevant=["1"], answer="anything"))
        assert result.answer_correct is None


class TestAggregate:
    def test_unparsed_replies_are_counted_not_scored_as_zero(self) -> None:
        """A reply nobody could read is a missing measurement, not a failure."""
        good = score_item(
            task(), DiscriminationOutput(relevant=["1", "3"], answer="Notre Dame")
        )
        bad_output, problems = parse_output("no json here", ["1", "2", "3", "4"])
        bad = score_item(task(), bad_output, problems)

        result = score("m", [good, bad])
        assert result.unparsed == 1
        assert result.overall.items == 1
        assert result.overall.precision == 1.0
        assert result.parse_problems == {"no-json": 1}

    def test_slices_are_reported_per_category_and_tier(self) -> None:
        scores: list[ItemScore] = [
            score_item(task(), DiscriminationOutput(relevant=["1", "3"], answer="Notre Dame")),
            score_item(
                task(
                    id="srd-test-2",
                    category=Category.WEB,
                    gold_answer=[],
                    noise_tier=NoiseTier.HARD,
                ),
                DiscriminationOutput(relevant=["2"], answer=""),
            ),
        ]
        result = score("m", scores)
        assert {s.name for s in result.by_category} == {"wikipedia", "web"}
        assert {s.name for s in result.by_tier} == {"easy", "hard"}


class TestJudging:
    """The judge's word only counts when the quote checks out."""

    def test_a_real_quote_verifies(self) -> None:
        verdict = verify(
            GroundednessVerdict(
                verdict=Verdict.CORRECT,
                claim="Criqui was born in Buffalo",
                candidate_id="1",
                quote="born in Buffalo, New York",
            ),
            task(),
        )
        assert verdict.quote_verified

    def test_a_fabricated_quote_is_discarded(self) -> None:
        verdict = verify(
            GroundednessVerdict(
                verdict=Verdict.CORRECT,
                claim="Criqui replaced Roberts in 1980",
                candidate_id="1",
                quote="Criqui replaced Roberts in 1980",
            ),
            task(),
        )
        assert not verdict.quote_verified

    def test_a_quote_from_the_wrong_candidate_is_discarded(self) -> None:
        verdict = verify(
            GroundednessVerdict(
                verdict=Verdict.CORRECT,
                claim="Roberts called Notre Dame football",
                candidate_id="2",
                quote="Tony Roberts called Notre Dame football",
            ),
            task(),
        )
        assert not verdict.quote_verified

    def test_whitespace_and_accents_do_not_break_a_faithful_quote(self) -> None:
        verdict = verify(
            GroundednessVerdict(
                verdict=Verdict.CORRECT,
                claim="x",
                candidate_id="1",
                quote="born in  Buffalo,\nNew York",
            ),
            task(),
        )
        assert verdict.quote_verified

    def test_an_unsupported_verdict_needs_no_quote(self) -> None:
        verdict = verify(
            GroundednessVerdict(verdict=Verdict.INCORRECT, claim="x"),
            task(),
        )
        assert verdict.quote_verified

    def test_the_prompt_shows_only_the_cited_candidates(self) -> None:
        """A judge given every candidate could ground a lucky answer."""
        prompt = build_prompt(task(), DiscriminationOutput(relevant=["1"], answer="x"))
        assert "Buffalo" in prompt
        assert "Apples are a fruit" not in prompt

    def test_a_run_with_one_fabricated_claim_is_not_grounded(self) -> None:
        reply = """{"verdicts": [
          {"claim": "a", "verdict": "correct", "candidate_id": "1",
           "quote": "born in Buffalo, New York", "reasoning": ""},
          {"claim": "b", "verdict": "incorrect", "candidate_id": "",
           "quote": "", "reasoning": ""}
        ]}"""
        run = judge_run(task=task(), reply=reply, model="m", judge_model="j")
        assert len(run.usable) == 2
        assert run.grounded is False

    def test_a_run_whose_verdicts_all_fail_verification_grounds_nothing(self) -> None:
        reply = """{"verdicts": [
          {"claim": "a", "verdict": "correct", "candidate_id": "1",
           "quote": "this sentence is not in the passage", "reasoning": ""}
        ]}"""
        run = judge_run(task=task(), reply=reply, model="m", judge_model="j")
        assert run.usable == []
        assert run.grounded is None

        rate, discarded = grounded_rate([run])
        assert rate is None
        assert discarded == 1

    def test_an_unreadable_judge_reply_yields_no_verdicts(self) -> None:
        assert parse_verdicts("I am not going to answer that") == []
        run = judge_run(task=task(), reply="nope", model="m", judge_model="j")
        assert run.error and run.grounded is None

    def test_the_prompt_version_travels_with_every_run(self) -> None:
        run = judge_run(task=task(), reply='{"verdicts": []}', model="m", judge_model="j")
        assert run.prompt_version == "groundedness-1"
        assert run.judge_model == "j"


class TestTypedJudge:
    """Jev returns a probability over text we supplied, so there is nothing
    for it to invent — only a vote to get wrong."""

    def test_the_state_carries_only_the_cited_results(self) -> None:
        from llmsearchbench.scoring.judging import typed_state

        state = typed_state(task(), DiscriminationOutput(relevant=["1"], answer="Buffalo"))
        assert "Buffalo, New York" in state
        assert "Apples are a fruit" not in state

    def test_one_question_per_cited_result_plus_an_overall_one(self) -> None:
        from llmsearchbench.scoring.judging import typed_questions

        questions = typed_questions(DiscriminationOutput(relevant=["1", "3"], answer="x"))
        assert set(questions) == {"supported_by_1", "supported_by_3", "supported_anywhere"}
        assert all(q["type"] == "noul" for q in questions.values())

    def test_probabilities_become_verdicts_with_a_band_of_not_sure(self) -> None:
        from llmsearchbench.scoring.judging import verdict_for

        assert verdict_for(0.95) is Verdict.CORRECT
        assert verdict_for(0.05) is Verdict.INCORRECT
        # The middle is the model saying it does not know, and rounding that to
        # a side would invent confidence nobody has.
        assert verdict_for(0.5) is Verdict.UNJUDGEABLE

    def test_a_run_is_recorded_with_its_probabilities(self) -> None:
        from llmsearchbench.scoring.judging import typed_run

        run = typed_run(
            task=task(),
            output=DiscriminationOutput(relevant=["1"], answer="Criqui is from Buffalo"),
            answers={
                "supported_by_1": {"type": "noul", "noul": 0.92},
                "supported_anywhere": {"type": "noul", "noul": 0.88},
            },
            model="m",
            judge_model="jev-1.13.0",
        )
        assert run.kind is JudgeKind.TYPED
        assert run.grounded is True
        assert [v.probability for v in run.verdicts] == [0.92, 0.88]
        # Nothing was quoted, so nothing needed checking.
        assert all(v.quote_verified for v in run.verdicts)

    def test_a_low_probability_fails_the_run(self) -> None:
        from llmsearchbench.scoring.judging import typed_run

        run = typed_run(
            task=task(),
            output=DiscriminationOutput(relevant=["1"], answer="Criqui won a Grammy"),
            answers={"supported_by_1": {"type": "noul", "noul": 0.02}},
            model="m",
            judge_model="jev-1.13.0",
        )
        assert run.grounded is False

    def test_an_answer_that_is_not_a_noul_is_ignored(self) -> None:
        from llmsearchbench.scoring.judging import typed_run

        run = typed_run(
            task=task(),
            output=DiscriminationOutput(relevant=["1"], answer="x"),
            answers={"supported_by_1": {"type": "choice", "choice": "yes"}},
            model="m",
            judge_model="jev-1.13.0",
        )
        assert run.verdicts == []
        assert run.grounded is None and run.error


class TestJevClient:
    def test_a_missing_key_fails_loudly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from llmsearchbench.harness.typesafe import NotConfiguredError

        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        with pytest.raises(NotConfiguredError, match="TYPESAFE_API_KEY"):
            from llmsearchbench.harness.typesafe import JevClient

            JevClient()

    def test_the_model_is_pinned_not_floating(self) -> None:
        """A released number cannot come from a model that moves under it."""
        from llmsearchbench.harness.typesafe import DEFAULT_MODEL

        assert DEFAULT_MODEL != "jev-latest"
        assert DEFAULT_MODEL.startswith("jev-")

    def test_an_unanswered_question_is_an_error_not_a_no(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silence about a question must never read as a 'no'."""
        import io
        import json as json_module

        from llmsearchbench.harness import typesafe
        from llmsearchbench.harness.typesafe import JevClient, JevError, noul

        class Response(io.BytesIO):
            def __enter__(self) -> Response:
                return self

            def __exit__(self, *_: object) -> None:
                return None

        body = json_module.dumps(
            {"answers": {"a": {"type": "noul", "noul": 0.9}}, "usage": {"input_tokens": 10}}
        ).encode()
        monkeypatch.setattr(typesafe.urllib.request, "urlopen", lambda *a, **k: Response(body))

        client = JevClient(api_key="test")
        with pytest.raises(JevError, match="unanswered question"):
            client.ask("some text", {"a": noul("is it?"), "b": noul("and this?")})

        # The one that was answered comes back intact.
        assert client.ask("some text", {"a": noul("is it?")})["a"]["noul"] == 0.9


class TestRunLoop:
    """The prompt, and what counts as a reply."""

    def test_the_prompt_carries_every_candidate_with_its_id(self) -> None:
        from llmsearchbench.harness.discrimination import build_prompt

        prompt = build_prompt(task())
        assert "[1]" in prompt and "[4]" in prompt
        assert "Apples are a fruit" in prompt
        assert "who replaced him" in prompt

    def test_the_prompt_never_leaks_the_grades(self) -> None:
        """The answer key travels in the same object; it must not reach the model.

        The gold answer itself is not secret — it is sitting in one of the
        candidates, which is what makes the item answerable. What must not
        leak is which candidate that is.
        """
        from llmsearchbench.harness.discrimination import build_prompt

        item = task()
        prompt = build_prompt(item)
        assert "supporting" not in prompt.lower()
        assert "grade" not in prompt.lower()
        for candidate_id, grade in item.relevance.items():
            assert f'"{candidate_id}": {grade}' not in prompt

    def test_an_empty_reply_is_a_failure_not_an_abstention(self) -> None:
        """Saying nothing is not the same as saying the results do not answer."""
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
        assert attempt.failed
        assert "length" in attempt.error

    def test_a_provider_error_is_recorded_rather_than_raised(self) -> None:
        from llmsearchbench.harness.adapters import Turn
        from llmsearchbench.harness.discrimination import run_task

        class Broken:
            def complete(self, prompt: str, temperature: float = 0.0) -> Turn:
                raise ConnectionError("the provider went away")

        attempt = run_task(task(), "m", Broken())
        assert attempt.failed and "ConnectionError" in attempt.error
