"""Admission rules for the tool-use-correctness task set.

Each rule is a named predicate returning a reason string when an item should be
dropped, or `None` to keep it. Naming them individually is what lets the build
report say *why* the pool shrank, rather than only that it did — see the
statistics table in the task's documentation page.

Every rule here exists because of something found in the source data. The
analysis behind them is in `docs/content/tasks/tool-use-correctness/building.mdx`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from typing import Any

#: One line of a source dataset, before it becomes a task. Keys vary by source,
#: so this stays loose on purpose; the filters below are what narrow it.
SourceRecord = dict[str, Any]

#: Wording that makes an answer true only at the moment it was written. A
#: 2023 "who is the richest man" gold answer is simply wrong today, so these
#: cannot be scored against a fixed gold.
TIME_RELATIVE = re.compile(
    r"\b(latest|most recent|currently|current|right now|as of (today|now)|"
    r"today|this (week|month|year|season)|so far this|upcoming|"
    r"newest|now|present|nowadays|these days|at the moment|to date|"
    r"how old is|how many .{0,30} are there)\b",
    re.IGNORECASE,
)

#: Superlatives over a changing population. "Richest man on earth" has a
#: different answer each year even though the wording never dates itself.
UNSTABLE_SUPERLATIVE = re.compile(
    r"\b(richest|largest|biggest|highest[- ]grossing|best[- ]selling|top[- ]selling|"
    r"most popular|most valuable|fastest|tallest building)\b",
    re.IGNORECASE,
)

Rule = Callable[[SourceRecord], str | None]


def fold(text: str) -> str:
    """Case, accent, and punctuation insensitive form, for answer matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", stripped.lower()).strip()


def passage_text(passage: object) -> str:
    """Flatten one context entry, whatever shape the source used for it.

    RetrievalQA ships five shapes: full objects, objects missing `id`/`score`,
    objects with a title but no `text` key, one empty object, and — for toolqa —
    bare strings. Anything reading `context` has to cope with all of them.
    """
    if isinstance(passage, str):
        return passage
    if isinstance(passage, dict):
        return f"{passage.get('title', '')} {passage.get('text', '')}"
    return ""


def context_blob(record: SourceRecord) -> str:
    return fold(" ".join(passage_text(p) for p in record.get("context", [])))


def answer_in_context(record: SourceRecord) -> bool:
    blob = context_blob(record)
    return any(fold(alias) in blob for alias in record["ground_truth"] if alias.strip())


# --- rules ---------------------------------------------------------------


def blank_alias(record: SourceRecord) -> str | None:
    """TriviaQA carries empty strings inside some alias lists."""
    if any(not alias.strip() for alias in record["ground_truth"]):
        return "blank-alias"
    return None


def leaked_csv_quoting(record: SourceRecord) -> str | None:
    """116 TriviaQA questions arrive wrapped in stray doubled quotes."""
    question = record["question"]
    if '""' in question or (question.startswith('"') and question.endswith('"')):
        return "leaked-quoting"
    return None


#: Leading articles carry no identifying information for this check.
_ARTICLE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)

#: PopQA is generated from a fixed set of templates over an entity. Matching
#: them explicitly beats hunting for the last preposition, which mis-fires on
#: titles that contain one — `School for Coquettes` yielded `Coquettes`.
_POPQA_TEMPLATES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^what is (.+?)'s occupation$",
        r"^what sport does (.+?) play$",
        r"^in what city was (.+?) born$",
        r"^in what country is (.+)$",
        r"^what is the capital of (.+)$",
        r"^what is the religion of (.+)$",
        r"^what genre is (.+)$",
        r"^what color is (.+)$",
        r"^who is the author of (.+)$",
        r"^who is the (?:father|mother) of (.+)$",
        r"^who was the (?:director|composer|producer) of (.+)$",
        r"^who was the screenwriter for (.+)$",
        r"^what is (.+)$",
    )
)


def popqa_entity(record: SourceRecord) -> str:
    """The subject PopQA templated its question over, or "" if no template fits."""
    question = record["question"].strip().rstrip("?").strip()
    for template in _POPQA_TEMPLATES:
        match = template.match(question)
        if match:
            # Only a possessive is stripped. `.strip("'s")` would also eat a
            # trailing plural, turning `Coquettes` into `Coquette`.
            return re.sub(r"'s$", "", match.group(1)).strip()
    return ""


def ambiguous_entity(record: SourceRecord) -> str | None:
    """PopQA templates over an entity name, and generic names are ambiguous.

    Two failure shapes, both fatal:

    * very short subjects — `What genre is VS?` appears twice in the source
      with contradictory gold answers;
    * common single words — `Who is the author of Eclipse?` has one gold
      answer and dozens of true ones, because the surface question has lost
      the entity id it was generated from.

    A subject therefore has to be either several words or a long one. That is
    a blunt instrument and it drops some fair questions, which is the right
    direction to err: an unanswerable item makes a model look worse than it is.
    """
    if record["data_source"] != "popqa":
        return None
    subject = _ARTICLE.sub("", popqa_entity(record))
    if not subject:
        return "unrecognised-template"
    if len(subject) < 4:
        return "ambiguous-short-entity"
    if len(subject.split()) < 2 and len(subject) < 10:
        return "ambiguous-generic-entity"
    return None


def disambiguation_alias(record: SourceRecord) -> str | None:
    """An alias carrying a Wikipedia disambiguation marker.

    These mark a failed entity link upstream: `What is a shapka?` carries the
    gold `Hat (disambiguation)`, and the answer set is then about the wrong
    page rather than about hats.
    """
    if any("(disambiguation)" in alias.lower() for alias in record["ground_truth"]):
        return "disambiguation-alias"
    return None


def time_relative(record: SourceRecord) -> str | None:
    """The gold was true when scraped and may not be true now."""
    if TIME_RELATIVE.search(record["question"]):
        return "time-relative"
    if UNSTABLE_SUPERLATIVE.search(record["question"]):
        return "unstable-superlative"
    return None


def synthetic_corpus(record: SourceRecord) -> str | None:
    """ToolQA questions are answerable only from invented private documents.

    They are fine for a fixed-corpus benchmark and wrong for this one: a real
    search tool cannot find Grace's calendar, so a model that correctly decides
    to search is then punished for failing to answer.
    """
    if record["data_source"] == "toolqa":
        return "synthetic-corpus"
    return None


def unsupported_by_context(record: SourceRecord) -> str | None:
    """No gold alias appears anywhere in the retrieved context.

    For the search bucket this is the main filter: roughly a third of the
    retrieval-required pool has an answer that its own context does not
    contain, through entity ambiguity, stale scrapes, or corrupted gold.
    """
    if not answer_in_context(record):
        return "answer-absent-from-context"
    return None


#: Applied in order; the first failure is what the build report records.
_COMMON_RULES: Sequence[Rule] = (
    blank_alias,
    leaked_csv_quoting,
    disambiguation_alias,
    ambiguous_entity,
    time_relative,
    synthetic_corpus,
    unsupported_by_context,
)

MEMORY_RULES: Sequence[Rule] = _COMMON_RULES
SEARCH_RULES: Sequence[Rule] = _COMMON_RULES


def first_failure(record: SourceRecord, rules: Sequence[Rule]) -> str | None:
    """The name of the first rule the record fails, or None if it passes all."""
    for rule in rules:
        reason = rule(record)
        if reason is not None:
            return reason
    return None
