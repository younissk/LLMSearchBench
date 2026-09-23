"""Groundedness: is each claim in the answer actually in the evidence?

This is the one number in the benchmark a model produces, so it is built to be
checked rather than trusted. A verdict has to name a candidate and quote the
span it rests on, and the quote is then looked for in that candidate's text. If
it is not there, the verdict is discarded — the judge cannot assert support
that does not exist, because the assertion has to survive a string search.

What the judge is *not* allowed to do:

* re-rank the candidates — TREC assessors already graded them, and a model
  overruling them would quietly replace human ground truth with machine ground
  truth;
* decide whether the answer is correct — that is a lenient string match against
  the gold answer, and a judge there would make the judge part of the score.

It rules on one question only: does this claim appear in the evidence cited.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from llmsearchbench.types.discrimination import DiscriminationTask
from llmsearchbench.types.enums import Verdict
from llmsearchbench.types.judging import (
    DiscriminationOutput,
    GroundednessVerdict,
    JudgeRun,
)

#: Bumped whenever the wording below changes. Verdicts carry it, so a rescored
#: release cannot silently mix two prompts.
PROMPT_VERSION = "groundedness-1"

#: The schema the judge is held to. Sent as a JSON Schema where the provider
#: enforces one, and pasted into the prompt where it does not.
VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdicts"],
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "verdict", "candidate_id", "quote", "reasoning"],
                "properties": {
                    "claim": {"type": "string"},
                    "verdict": {"enum": ["correct", "incorrect", "unjudgeable"]},
                    "candidate_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "reasoning": {"type": "string"},
                },
            },
        }
    },
}

JUDGE_INSTRUCTIONS = """\
You are checking whether an answer is supported by the search results it was \
given. You are not judging whether the answer is true, and you are not judging \
which results are relevant. One question only: is each claim in the answer \
stated in the results?

For every distinct factual claim in the answer, return one verdict:

- "correct" — the claim is stated in one of the results. Name that result in \
`candidate_id` and copy the exact sentence or phrase that states it into \
`quote`. The quote must appear character for character in that result; it is \
checked automatically, and a verdict whose quote cannot be found is thrown away.
- "incorrect" — the claim is not in any result. Leave `candidate_id` and \
`quote` empty.
- "unjudgeable" — the claim is too vague to check either way.

Do not paraphrase in `quote`. Do not quote the question. Do not invent a \
candidate id that is not in the list.
"""


def fold(text: str) -> str:
    """Whitespace- and accent-insensitive form, for finding a quote.

    A judge that copies a span faithfully but normalises a dash or collapses a
    line break has still copied it faithfully. Anything looser than this would
    start accepting paraphrase, which is the thing being guarded against.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def build_prompt(task: DiscriminationTask, output: DiscriminationOutput) -> str:
    """The judging prompt for one answer.

    Only the candidates the model cited are shown. A judge given all twenty
    could find support in a passage the model never used, which would score a
    lucky answer as a grounded one.
    """
    cited = [c for c in task.candidates if c.id in set(output.relevant)]
    results = "\n\n".join(f"[{c.id}] {c.text}" for c in cited) or "(the model cited nothing)"
    return (
        f"{JUDGE_INSTRUCTIONS}\n"
        f"QUESTION\n{task.question}\n\n"
        f"RESULTS THE MODEL CITED\n{results}\n\n"
        f"ANSWER TO CHECK\n{output.answer}\n"
    )


def verify(verdict: GroundednessVerdict, task: DiscriminationTask) -> GroundednessVerdict:
    """Look for the judge's quote where the judge said it was.

    Returns the verdict with `quote_verified` set. A `correct` verdict without
    a findable quote is left unverified, which drops it from the score: the
    judge made a claim about a document, and the document is right there.
    """
    if verdict.verdict is not Verdict.CORRECT:
        # Nothing to find: "incorrect" and "unjudgeable" rest on absence, and
        # absence cannot be quoted.
        return verdict.model_copy(update={"quote_verified": True})

    candidate = next((c for c in task.candidates if c.id == verdict.candidate_id), None)
    if candidate is None or not verdict.quote.strip():
        return verdict.model_copy(update={"quote_verified": False})

    found = fold(verdict.quote) in fold(candidate.text)
    return verdict.model_copy(update={"quote_verified": found})


def parse_verdicts(text: str) -> list[GroundednessVerdict]:
    """Read a judge's reply. A reply that cannot be read yields no verdicts."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return []
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, dict):
        return []

    verdicts: list[GroundednessVerdict] = []
    for entry in raw.get("verdicts") or []:
        if not isinstance(entry, dict):
            continue
        try:
            verdicts.append(
                GroundednessVerdict(
                    verdict=Verdict(str(entry.get("verdict", "unjudgeable"))),
                    claim=str(entry.get("claim") or "").strip() or "(unstated claim)",
                    candidate_id=str(entry.get("candidate_id") or "").strip().strip("[]"),
                    quote=str(entry.get("quote") or ""),
                    reasoning=str(entry.get("reasoning") or ""),
                )
            )
        except ValueError:
            continue
    return verdicts


def judge_run(
    *,
    task: DiscriminationTask,
    reply: str,
    model: str,
    judge_model: str,
) -> JudgeRun:
    """Turn one judge reply into a checked record.

    The answer that was judged is not needed here — it went into the prompt.
    What comes back is checked against the task's candidates, which is the only
    thing a quote can be verified against.
    """
    verdicts = [verify(v, task) for v in parse_verdicts(reply)]
    return JudgeRun(
        task_id=task.id,
        model=model,
        judge_model=judge_model,
        prompt_version=PROMPT_VERSION,
        verdicts=verdicts,
        error="" if verdicts else "no verdicts could be read from the judge's reply",
    )


def grounded_rate(runs: Sequence[JudgeRun]) -> tuple[float | None, int]:
    """Share of answers whose every checkable claim was supported.

    Also returns how many verdicts were discarded for an unfindable quote,
    which belongs in the published result: it is the judge's own error rate,
    measured rather than assumed.
    """
    discarded = sum(1 for run in runs for v in run.verdicts if not v.quote_verified)
    ruled = [run.grounded for run in runs if run.grounded is not None]
    if not ruled:
        return None, discarded
    return sum(1 for value in ruled if value) / len(ruled), discarded
