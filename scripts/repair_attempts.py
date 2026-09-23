"""Bring already-recorded attempts up to the current reading of a reply.

    uv run python scripts/repair_attempts.py [--dry-run]

Two things were being recorded wrongly, and both are visible in what was
already saved, so most of this costs nothing to fix:

1. **A call written into the reply text** was recorded as no call at all. The
   answer text is stored, so the call can be read back out of it — no rerun.
2. **A reply with no text and no call** was recorded as a successful item, and
   scored as "chose not to search", which is right on two buckets out of three.
   Nothing is recoverable there: the model never decided. Those rows are turned
   into failures, which a rerun retries.

Safe to run more than once. Rewrites each file in place, atomically.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llmsearchbench.harness.openai_compat import parse_text_calls
from llmsearchbench.paths import RESULTS
from llmsearchbench.storage import write_jsonl


def repaired(row: dict[str, object]) -> tuple[dict[str, object], str | None]:
    """One attempt, and what was done to it."""
    if row.get("error") or row.get("calls"):
        return row, None

    answer = str(row.get("answer") or "")
    calls = parse_text_calls(answer)
    if calls:
        row["calls"] = [call.model_dump() for call in calls]
        return row, "text-call"

    if not answer.strip():
        stop = str(row.get("stop_reason") or "")
        row["error"] = "no answer and no tool call" + (
            f" (stop reason {stop!r})" if stop else ""
        )
        return row, "no-decision"

    return row, None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument(
        "--results", type=Path, default=RESULTS / "local", help="where attempts live"
    )
    args = parser.parse_args()

    totals = {"text-call": 0, "no-decision": 0}
    for path in sorted(args.results.glob("*-attempts.jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        counts = {"text-call": 0, "no-decision": 0}
        out = []
        for row in rows:
            fixed, what = repaired(row)
            if what:
                counts[what] += 1
            out.append(fixed)

        if not any(counts.values()):
            continue
        totals = {key: totals[key] + counts[key] for key in totals}
        model = path.stem.replace("--", "/").replace("-attempts", "")
        print(
            f"{model:45} {counts['text-call']:4} text call(s), "
            f"{counts['no-decision']:4} non-decision(s)"
        )
        if not args.dry_run:
            write_jsonl(path, out)

    print(
        f"\n{totals['text-call']} call(s) recovered from reply text; "
        f"{totals['no-decision']} item(s) marked for a rerun."
    )
    if args.dry_run:
        print("dry run: nothing written")


if __name__ == "__main__":
    main()
