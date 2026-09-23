"""Write gold answers for the web queries, using Claude as the annotator.

    uv run python scripts/annotate_web_answers.py [--batch 8] [--dry-run]

TREC judged which passages answer a query, never what the answer is, so the web
category has nothing for an answer-only score to compare against. This asks
Claude to read the passages a human already graded as relevant and say what
answer they give.

Three rules make the result usable as a label rather than as an opinion:

1. The annotator sees only the passages a human graded 2 or 3. It is extracting
   what those say, not answering from what it knows.
2. Every answer must come with a verbatim quote from a named passage, and this
   script checks that the quote is really in that passage. A quote that is not
   found means the item is dropped, not trusted.
3. An annotator that cannot find a crisp answer must say so, and that query is
   dropped. A broad query like "anthropological definition of environment" has
   no single short answer, and inventing one would put a made-up label into the
   benchmark.

Every accepted answer is written with the model that produced it, the date, and
the quote it rests on, so a reader can check any of them by hand. The result is
a *model-written* label and the task set records it as such — it is weaker
evidence than HotpotQA's own answers and is never presented as equal to them.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
from datetime import date
from typing import Any

from llmsearchbench.paths import REPO_ROOT, TASKS
from llmsearchbench.storage import read_jsonl
from llmsearchbench.types.discrimination import DiscriminationTask

OUT = REPO_ROOT / "data" / "web_answers.json"
LOCAL_SET = TASKS / "local" / "search-result-discrimination-local.jsonl"

#: Pinned. A label written by a model is only interpretable if the model is
#: named, the same reason prices carry a date.
ANNOTATOR = "claude-sonnet-5"

#: The longest answer that can be checked by containment. A model asked "define
#: visceral" will phrase a definition its own way, and no string match can tell
#: a good paraphrase from a bad one — so a query whose answer needs more than
#: this is dropped rather than scored badly by an unfit measure.
MAX_WORDS = 6

#: Bumped whenever the instructions below change.
PROMPT_VERSION = "web-answers-2"

INSTRUCTIONS = """\
You are writing answer keys for a search benchmark.

For each QUERY below you are given the passages that human assessors judged \
relevant to it. Say what answer those passages give.

Rules:
- Use only the passages shown. Do not use anything you know beyond them.
- The answer must be SIX WORDS OR FEWER: a name, a number, a date, a short \
noun phrase. Not a definition and not a sentence.
- If the query asks for a definition or an explanation, its answer cannot be \
six words, so set "answerable" to false.
- If the answer is just "yes" or "no", set "answerable" to false — a coin gets \
those right half the time.
- Quote the exact words from one passage that state the answer. The quote is \
checked against the passage automatically; if it is not found verbatim, the \
query is thrown out.
- If the passages do not give one short, checkable answer — the query is too \
broad, or they discuss a topic without answering anything specific — set \
"answerable" to false and leave the answer empty. This is expected for some \
queries and is better than guessing.

Reply with one JSON object and nothing else:

{"answers": [
  {"query_id": "19335", "answerable": true, "answer": "...", \
"passage_id": "3", "quote": "exact words from passage 3"},
  {"query_id": "1037798", "answerable": false, "answer": "", \
"passage_id": "", "quote": ""}
]}
"""


def fold(text: str) -> str:
    """Whitespace- and accent-insensitive, for finding a quote."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def web_queries() -> dict[str, DiscriminationTask]:
    """One item per web query — the tier carrying the most relevant passages."""
    best: dict[str, DiscriminationTask] = {}
    for row in read_jsonl(LOCAL_SET):
        task = DiscriminationTask.model_validate(row)
        if task.category != "web":
            continue
        current = best.get(task.source_id)
        if current is None or len(task.supporting_ids) > len(current.supporting_ids):
            best[task.source_id] = task
    return dict(sorted(best.items(), key=lambda kv: int(kv[0])))


def render(tasks: list[DiscriminationTask]) -> str:
    """One batch of queries with their human-judged relevant passages."""
    blocks = []
    for task in tasks:
        passages = "\n".join(
            f"  [{c.id}] {c.text}" for c in task.candidates if c.id in task.supporting_ids
        )
        blocks.append(f"QUERY {task.source_id}: {task.question}\n{passages}")
    return INSTRUCTIONS + "\n" + "\n\n".join(blocks)


def ask_claude(prompt: str) -> str:
    """One `claude -p` call. Returns the assistant's text."""
    result = subprocess.run(
        ["claude", "-p", "--model", ANNOTATOR, "--output-format", "json"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr[:300]}")
    body = json.loads(result.stdout)
    return str(body.get("result") or "")


def parse(text: str) -> list[dict[str, Any]]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    answers = parsed.get("answers")
    return [a for a in answers if isinstance(a, dict)] if isinstance(answers, list) else []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, default=8, help="queries per call")
    parser.add_argument("--dry-run", action="store_true", help="print one prompt and stop")
    args = parser.parse_args()

    queries = web_queries()
    tasks = list(queries.values())
    print(f"{len(tasks)} web query/queries to annotate, {args.batch} per call")

    if args.dry_run:
        print("\n" + render(tasks[: args.batch])[:2000])
        return

    today = date.today().isoformat()
    accepted: dict[str, dict[str, object]] = {}
    unanswerable: list[str] = []
    rejected: list[str] = []

    for start in range(0, len(tasks), args.batch):
        batch = tasks[start : start + args.batch]
        answers = parse(ask_claude(render(batch)))
        by_id = {task.source_id: task for task in batch}

        for answer in answers:
            query_id = str(answer.get("query_id", "")).strip()
            task = by_id.get(query_id)
            if task is None:
                rejected.append(f"{query_id}: not in this batch")
                continue
            if not answer.get("answerable"):
                unanswerable.append(query_id)
                continue

            text = str(answer.get("answer") or "").strip()
            quote = str(answer.get("quote") or "").strip()
            passage_id = str(answer.get("passage_id") or "").strip().strip("[]")
            passage = next((c for c in task.candidates if c.id == passage_id), None)

            if not text or passage is None:
                rejected.append(f"{query_id}: no answer or unknown passage {passage_id!r}")
                continue
            if fold(quote) not in fold(passage.text):
                rejected.append(f"{query_id}: quote not found in passage {passage_id!r}")
                continue
            if len(text.split()) > MAX_WORDS:
                rejected.append(f"{query_id}: {len(text.split())} words, too long to check")
                continue
            if fold(text) in {"yes", "no"}:
                rejected.append(f"{query_id}: yes/no answer")
                continue

            accepted[query_id] = {
                "query": task.question,
                "answer": text,
                "quote": quote,
                "passage_source_id": passage.source_id,
                "annotator": ANNOTATOR,
                "prompt_version": PROMPT_VERSION,
                "annotated": today,
            }
        print(
            f"  {start + len(batch):3}/{len(tasks)} queries seen · "
            f"{len(accepted)} kept · {len(unanswerable)} unanswerable · "
            f"{len(rejected)} rejected"
        )

    OUT.write_text(json.dumps(accepted, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT} ({len(accepted)} answer(s))")
    print(
        f"  {len(unanswerable)} query/queries have no short checkable answer: "
        f"{', '.join(unanswerable[:8])}"
    )
    for line in rejected[:8]:
        print(f"  rejected {line}")


if __name__ == "__main__":
    main()
