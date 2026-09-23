"""Pull the judged passages out of the MS MARCO collection.

    uv run python scripts/extract_judged_passages.py

The TREC Deep Learning judgements name passages by id; the text lives in the
MS MARCO passage collection, which is 987 MB compressed and 3.06 GB inside.
Only the 20,349 judged passages are ever needed, so this streams the archive
once and writes those to `data/processed/msmarco-judged-passages.jsonl.gz`
(2.5 MB).

Run it after `make data` and before building the search-result-discrimination
task set. The whole scan takes about twenty seconds.
"""

from __future__ import annotations

import gzip
import json
import tarfile
import time

from llmsearchbench.paths import DATA_PROCESSED, DATA_RAW

COLLECTION = DATA_RAW / "msmarco" / "collection.tar.gz"
QRELS = (
    DATA_RAW / "trec-dl" / "2019qrels-pass.txt",
    DATA_RAW / "trec-dl" / "2020qrels-pass.txt",
)
OUT = DATA_PROCESSED / "msmarco-judged-passages.jsonl.gz"


def judged_ids() -> set[str]:
    """Every passage id either year's assessors looked at."""
    wanted: set[str] = set()
    for path in QRELS:
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing - run `make data` first.")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                wanted.add(line.split()[2])
    return wanted


def main() -> None:
    if not COLLECTION.exists():
        raise FileNotFoundError(f"{COLLECTION} is missing - run `make data` first.")

    wanted = judged_ids()
    print(f"{len(wanted)} judged passage(s) to find")

    started = time.time()
    found: dict[str, str] = {}
    with tarfile.open(COLLECTION, "r:gz") as archive:
        member = archive.next()
        if member is None:
            raise RuntimeError(f"{COLLECTION} is empty")
        handle = archive.extractfile(member)
        if handle is None:
            raise RuntimeError(f"{member.name} is not a file")
        for raw in handle:
            passage_id, _, text = raw.decode("utf-8").partition("\t")
            if passage_id in wanted:
                found[passage_id] = text.strip()
                # Stop as soon as the last one turns up rather than reading the
                # remaining millions of passages.
                if len(found) == len(wanted):
                    break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as out:
        for passage_id, text in sorted(found.items(), key=lambda kv: int(kv[0])):
            out.write(json.dumps({"id": passage_id, "text": text}) + "\n")

    missing = len(wanted) - len(found)
    print(
        f"wrote {OUT} - {len(found)} passage(s) in {time.time() - started:.0f}s"
        + (f", {missing} not in the collection" if missing else "")
    )


if __name__ == "__main__":
    main()
