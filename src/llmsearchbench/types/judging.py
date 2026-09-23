"""What a model answers with, and what a judge is allowed to say about it.

Two kinds of record live here, and the difference matters:

* `DiscriminationOutput` is what the model under test produced — a ranking, the
  candidates it would cite, and an answer. Everything scored from it is
  arithmetic against labels a person wrote.
* `GroundednessVerdict` is a *judge's* opinion, and it is the only place in
  this benchmark where a model's word counts toward a number. So it is shaped
  to be checkable: a verdict must quote the span it relies on, verbatim, from
  the candidate it names. A quote that is not in that candidate is discarded
  rather than believed.
"""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types.base import BenchModel
from llmsearchbench.types.enums import Verdict


class ParseProblem(BenchModel):
    """Why a reply could not be read, when it could not."""

    #: `no-json`, `bad-json`, `missing-field`, `unknown-candidate`, `duplicate`.
    kind: str = Field(min_length=1)
    detail: str = ""


class DiscriminationOutput(BenchModel):
    """One model's answer to one candidate set.

    The schema the model is asked for, and the schema its reply is validated
    against. Ids are strings because that is what the candidates use; a model
    that returns integers is normalised rather than failed, since the number is
    unambiguous either way.
    """

    #: Every candidate id, best evidence first. May be empty when the model
    #: only names the relevant ones.
    ranking: list[str] = Field(default_factory=list)
    #: The candidates it would actually cite. Empty means "these results do not
    #: answer the question", which is the right answer on the no_answer items.
    relevant: list[str] = Field(default_factory=list)
    #: The answer those candidates support, or an explicit refusal.
    answer: str = ""

    @property
    def abstained(self) -> bool:
        return not self.relevant


class GroundednessVerdict(BenchModel):
    """A judge's ruling on one claim in one answer.

    `quote` is the load-bearing field. It must appear character for character
    inside the candidate named by `candidate_id`, and the harness checks that
    rather than taking the judge's word for it — which turns "the judge thinks
    this is supported" into "this span exists and says so".
    """

    verdict: Verdict
    #: The claim from the answer being checked.
    claim: str = Field(min_length=1)
    #: Which candidate is said to support it. Empty when the verdict is that
    #: nothing does.
    candidate_id: str = ""
    #: A span copied out of that candidate, verbatim.
    quote: str = ""
    reasoning: str = ""

    #: Set by the harness, not the judge: False when the quote could not be
    #: found in the cited candidate. Such a verdict does not count.
    quote_verified: bool = False


class JudgeRun(BenchModel):
    """Every verdict for one item, with what produced them.

    The judge is pinned the way prices are: a number produced by a model is
    only interpretable if you know which model and which prompt produced it.
    """

    task_id: str = Field(min_length=1)
    #: The model whose answer was judged.
    model: str = Field(min_length=1)
    #: The judge, exactly as called.
    judge_model: str = Field(min_length=1)
    #: Bumped whenever the judging prompt changes, so old verdicts are not
    #: silently compared with new ones.
    prompt_version: str = Field(min_length=1)
    verdicts: list[GroundednessVerdict] = Field(default_factory=list)
    error: str = ""

    @property
    def usable(self) -> list[GroundednessVerdict]:
        """Verdicts whose quote was found where the judge said it was."""
        return [v for v in self.verdicts if v.quote_verified]

    @property
    def grounded(self) -> bool | None:
        """True when every checkable claim was supported.

        None when nothing was checkable — no usable verdict, or every one
        `unjudgeable`. A run with no evidence is not a pass.
        """
        ruled = [v for v in self.usable if v.verdict is not Verdict.UNJUDGEABLE]
        if not ruled:
            return None
        return all(v.verdict is Verdict.CORRECT for v in ruled)
