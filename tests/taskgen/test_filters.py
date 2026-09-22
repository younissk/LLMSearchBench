"""The admission rules, each of which exists because of a defect in the source."""

from __future__ import annotations

import pytest

from llmsearchbench.taskgen.filters import (
    MEMORY_RULES,
    ambiguous_entity,
    answer_in_context,
    blank_alias,
    disambiguation_alias,
    first_failure,
    fold,
    leaked_csv_quoting,
    passage_text,
    popqa_entity,
    synthetic_corpus,
    time_relative,
)


def record(**overrides: object) -> dict:
    base: dict = {
        "question": "In what city was Aarno Maliniemi born?",
        "ground_truth": ["Oulu"],
        "data_source": "popqa",
        "context": [{"title": "Aarno Maliniemi", "text": "born in Oulu"}],
    }
    base.update(overrides)
    return base


class TestPassageText:
    def test_handles_every_shape_the_source_ships(self) -> None:
        """Five shapes exist in RetrievalQA; a reader that assumes one crashes."""
        assert passage_text("a bare string") == "a bare string"
        assert passage_text({"title": "T", "text": "X"}).strip() == "T X"
        assert passage_text({"title": "T"}).strip() == "T"
        assert passage_text({}).strip() == ""
        assert passage_text(None) == ""


class TestFold:
    def test_strips_accents_and_punctuation(self) -> None:
        assert fold("Leoš Janáček!") == "leos janacek"

    def test_is_case_insensitive(self) -> None:
        assert fold("VALLETTA") == fold("Valletta")


class TestBlankAlias:
    def test_rejects_an_empty_string_alias(self) -> None:
        """TriviaQA ships alias lists containing empty strings."""
        assert blank_alias(record(ground_truth=["", "XXXII"])) == "blank-alias"

    def test_accepts_a_clean_list(self) -> None:
        assert blank_alias(record(ground_truth=["Oulu"])) is None


class TestLeakedQuoting:
    def test_rejects_doubled_quotes(self) -> None:
        bad = record(question='"What does ""Sinn Fein"" mean?"')
        assert leaked_csv_quoting(bad) == "leaked-quoting"

    def test_accepts_a_quote_used_normally(self) -> None:
        assert leaked_csv_quoting(record(question='Who said "hello"?')) is None


class TestAmbiguousEntity:
    def test_rejects_a_two_character_subject(self) -> None:
        """`What genre is VS?` appears twice with contradictory gold answers."""
        assert ambiguous_entity(record(question="What genre is VS?")) == (
            "ambiguous-short-entity"
        )

    def test_rejects_a_common_single_word_title(self) -> None:
        assert ambiguous_entity(record(question="Who is the author of Eclipse?")) == (
            "ambiguous-generic-entity"
        )

    def test_accepts_a_multi_word_title(self) -> None:
        item = record(question="Who is the author of School for Coquettes?")
        assert ambiguous_entity(item) is None

    def test_a_leading_article_does_not_rescue_a_short_title(self) -> None:
        """`The Latimers` is no less ambiguous than `Latimers`, so the article
        is stripped before the check. This drops some fair questions, which is
        the right direction to err: an unanswerable item makes a model look
        worse than it is."""
        item = record(question="Who is the author of The Latimers?")
        assert ambiguous_entity(item) == "ambiguous-generic-entity"

    def test_accepts_a_long_single_word(self) -> None:
        assert ambiguous_entity(record(question="What is the capital of Turkmenistan?")) is None

    def test_only_applies_to_popqa(self) -> None:
        """Other sources write real questions rather than templating an entity in."""
        assert ambiguous_entity(record(question="Who is X?", data_source="triviaqa")) is None


class TestPopqaEntity:
    @pytest.mark.parametrize(
        ("question", "expected"),
        [
            ("Who is the author of Template?", "Template"),
            ("What genre is VS?", "VS"),
            ("What is the capital of Kerman Province?", "Kerman Province"),
            ("In what city was Aarno Maliniemi born?", "Aarno Maliniemi"),
            ("What is Arafan Camara's occupation?", "Arafan Camara"),
            ("Who is the author of School for Coquettes?", "School for Coquettes"),
        ],
    )
    def test_extracts_the_templated_subject(self, question: str, expected: str) -> None:
        assert popqa_entity(record(question=question)) == expected

    def test_a_title_containing_a_preposition_survives_intact(self) -> None:
        """Hunting for the last preposition turned `School for Coquettes` into
        `Coquettes`, and a trailing-character strip then made it `Coquette`."""
        item = record(question="Who is the author of School for Coquettes?")
        assert popqa_entity(item) == "School for Coquettes"

    def test_an_unrecognised_template_is_rejected_rather_than_guessed(self) -> None:
        item = record(question="Something entirely different about Paris?")
        assert ambiguous_entity(item) == "unrecognised-template"


class TestTimeRelative:
    @pytest.mark.parametrize(
        "question",
        [
            "What is the latest highest-grossing movie?",
            "Who is the most recent player to score 60 points?",
            "What Berber year corresponds to the present year?",
            "How old is Donald Trump?",
        ],
    )
    def test_rejects_answers_that_expire(self, question: str) -> None:
        assert time_relative(record(question=question)) is not None

    def test_accepts_a_dated_fact(self) -> None:
        assert time_relative(record(question="Who won the 1998 World Cup?")) is None

    def test_rejects_an_unstable_superlative(self) -> None:
        """`Who is the richest man` dates itself without any time word."""
        assert time_relative(record(question="Who is the richest man on earth?")) == (
            "unstable-superlative"
        )


class TestDisambiguationAlias:
    def test_rejects_a_failed_entity_link(self) -> None:
        bad = record(ground_truth=["hat", "Hat (disambiguation)"])
        assert disambiguation_alias(bad) == "disambiguation-alias"


class TestSyntheticCorpus:
    def test_rejects_toolqa(self) -> None:
        """A real search tool cannot find an invented private calendar."""
        assert synthetic_corpus(record(data_source="toolqa")) == "synthetic-corpus"

    def test_accepts_web_sourced_datasets(self) -> None:
        assert synthetic_corpus(record(data_source="realtimeqa")) is None


class TestAnswerInContext:
    def test_true_when_an_alias_appears(self) -> None:
        assert answer_in_context(record())

    def test_folds_accents_before_comparing(self) -> None:
        item = record(
            ground_truth=["Leos Janacek"],
            context=[{"title": "Leoš Janáček", "text": "composer"}],
        )
        assert answer_in_context(item)

    def test_false_when_the_context_never_says_it(self) -> None:
        item = record(ground_truth=["monk"], context=[{"title": "X", "text": "a footballer"}])
        assert not answer_in_context(item)


class TestFirstFailure:
    def test_reports_the_first_rule_that_rejects(self) -> None:
        item = record(ground_truth=[""], question='"bad ""quoting"" too"')
        assert first_failure(item, MEMORY_RULES) == "blank-alias"

    def test_returns_none_for_a_clean_record(self) -> None:
        assert first_failure(record(), MEMORY_RULES) is None
