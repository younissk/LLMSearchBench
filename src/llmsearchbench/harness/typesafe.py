"""Calling Jev, TypeSafe AI's decision model.

Jev is not a chat model and is not called like one. It takes a block of text
(`state`) and a set of typed questions about it, and returns an answer per
question with a probability — a yes/no ("noul"), a choice from a set you
defined, or a score on a rubric. It cannot return anything outside that schema,
and it cannot return prose at all.

That last part is why it is the judge here. A generative judge has to be made
honest — asked to quote its evidence so the quote can be checked. Jev is never
given the chance: the harness supplies the text, Jev votes on it, and there is
no span for it to invent.

Every question is answered in one parallel pass, so a whole item costs one
request.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from llmsearchbench.harness.openai_compat import (
    BACKOFF,
    DEADLINE,
    SOCKET_TIMEOUT,
    RequestTimeoutError,
    read_with_deadline,
    retry_after,
)

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
KEY_ENV = "TYPESAFE_API_KEY"

#: Pinned, not `jev-latest`. A released number has to come from a model that
#: cannot change underneath it, the same reason dataset files carry a checksum.
DEFAULT_MODEL = "jev-1.13.0"


class JevError(RuntimeError):
    """The decision model refused the request or could not be reached."""


class NotConfiguredError(RuntimeError):
    """No credential for TypeSafe."""


def noul(instructions: str) -> dict[str, str]:
    """A yes/no question. The answer is P(true), not a word."""
    return {"type": "noul", "instructions": instructions}


def choice(instructions: str, criteria: dict[str, str]) -> dict[str, Any]:
    """One option from a fixed set, with a probability per option."""
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def score(instructions: str, criteria: list[str]) -> dict[str, Any]:
    """A position on an ordered rubric, lowest level first."""
    return {"type": "score", "instructions": instructions, "criteria": criteria}


class JevClient:
    """One call: some text, some typed questions, some probabilities back."""

    def __init__(self, model: str = DEFAULT_MODEL, *, api_key: str | None = None) -> None:
        key = (api_key or os.environ.get(KEY_ENV, "")).strip()
        if not key:
            raise NotConfiguredError(
                f"{KEY_ENV} is not set. Put it in .env or export it; see .env.example."
            )
        self._key = key
        self.model = model

    def ask(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Put every question to one block of text.

        Returns the `answers` map keyed exactly as `questions` was. A missing
        key is a failure rather than a default: a question that was not
        answered must not read as a 'no'.
        """
        payload = {"model": self.model, "state": state, "questions": questions}
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._key}",
            },
            method="POST",
        )

        for wait in (*BACKOFF, None):
            deadline = time.monotonic() + DEADLINE
            try:
                with urllib.request.urlopen(request, timeout=SOCKET_TIMEOUT) as response:
                    body: dict[str, Any] = json.loads(read_with_deadline(response, deadline))
                break
            except urllib.error.HTTPError as error:
                detail = error.read()[:400].decode(errors="replace")
                if error.code == 429 and wait is not None:
                    time.sleep(retry_after(error) or wait)
                    continue
                raise JevError(f"{error.code}: {detail}") from error
            except urllib.error.URLError as error:
                raise JevError(f"unreachable: {error.reason}") from error
            except RequestTimeoutError as error:
                raise JevError(str(error)) from error
            except TimeoutError as error:
                raise JevError(f"socket timed out after {SOCKET_TIMEOUT:.0f}s") from error

        answers = body.get("answers")
        if not isinstance(answers, dict):
            raise JevError("response carried no answers")

        missing = set(questions) - set(answers)
        if missing:
            raise JevError(f"unanswered question(s): {', '.join(sorted(missing))}")
        return answers

    @staticmethod
    def probability(answer: dict[str, Any]) -> float | None:
        """P(true) from a noul answer, or None when the answer is not one."""
        value = answer.get("noul")
        return float(value) if isinstance(value, int | float) else None
