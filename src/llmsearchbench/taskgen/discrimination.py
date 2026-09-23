"""Building the search-result-discrimination task set.

Three categories, from two sources, and no retriever anywhere in the pipeline:

* **web** — TREC Deep Learning 2019 and 2020 passage judgements. Every
  candidate carries a graded human relevance label, and the non-relevant ones
  were *retrieved for that query*, which makes them hard negatives by
  construction rather than by our choosing.
* **no_answer** — the same queries, with only their human-judged non-relevant
  passages. Nothing is invented: a person read each of these passages against
  this question and said no.
* **wikipedia** — HotpotQA's distractor setting, where two of ten paragraphs
  carry the answer and the other eight were TF-IDF neighbours of the question.

Labels are marked `human` or `derived` and never mixed into one number:
TREC's grades are direct relevance judgements, HotpotQA's are inferred from its
supporting facts, and those are different kinds of evidence.

Deterministic given a seed: same inputs and seed, same task set, byte for byte.
"""

from __future__ import annotations

import collections
import gzip
import hashlib
import json
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import Field

from llmsearchbench.paths import DATA_PROCESSED, DATA_RAW
from llmsearchbench.storage import write_jsonl
from llmsearchbench.types import BenchModel
from llmsearchbench.types.discrimination import (
    Candidate,
    Category,
    DiscriminationTask,
    LabelSource,
    NoiseTier,
)

TREC = DATA_RAW / "trec-dl"
HOTPOT = DATA_RAW / "hotpotqa" / "hotpot-distractor-validation.parquet"
JUDGED_PASSAGES = DATA_PROCESSED / "msmarco-judged-passages.jsonl.gz"

#: Held fixed so a rebuild reproduces the shipped set.
DEFAULT_SEED = 20260923

#: How many candidates each tier shows. The point of having tiers is to see
#: where a model stops coping, so the counts are far apart rather than adjacent.
TIER_SIZES: dict[NoiseTier, int] = {
    NoiseTier.EASY: 5,
    NoiseTier.MEDIUM: 10,
    NoiseTier.HARD: 20,
}

#: At most this many relevant candidates per item. A question with fourteen
#: relevant passages is a different task — summarising, not discriminating.
MAX_RELEVANT = 4

#: Passage length bounds, in characters. Below the floor a passage is a
#: fragment with nothing to judge; above the ceiling one candidate crowds out
#: the rest of the set.
MIN_TEXT, MAX_TEXT = 120, 2000

#: How many of each category to build. The source caps the web category:
#: TREC 2019 and 2020 judged 97 queries between them, 40 of which are reserved
#: for the no-answer category, and each of the remaining 57 is built at all
#: three noise tiers.
DEFAULT_WEB = 171
DEFAULT_NO_ANSWER = 40
DEFAULT_WIKIPEDIA = 120


class Rejection(BenchModel):
    """One named admission rule and how many candidates it turned away."""

    rule: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    count: int = Field(ge=0)


class BuildReport(BenchModel):
    """Where every candidate went, so the published counts can be checked."""

    seed: int
    counts: dict[str, int] = Field(default_factory=dict)
    tiers: dict[str, int] = Field(default_factory=dict)
    label_sources: dict[str, int] = Field(default_factory=dict)
    candidates_total: int = Field(default=0, ge=0)
    relevant_total: int = Field(default=0, ge=0)
    dropped: list[Rejection] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Recorder:
    """Counts rejections by rule, so a build explains itself."""

    def __init__(self) -> None:
        self._counts: collections.Counter[tuple[str, str]] = collections.Counter()

    def drop(self, rule: str, reason: str) -> None:
        self._counts[(rule, reason)] += 1

    def rejections(self) -> list[Rejection]:
        return [
            Rejection(rule=rule, reason=reason, count=count)
            for (rule, reason), count in sorted(self._counts.items(), key=lambda kv: -kv[1])
        ]


# --- sources ----------------------------------------------------------------


def read_qrels(path: Path) -> dict[str, dict[str, int]]:
    """TREC qrels: query id -> passage id -> grade."""
    qrels: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        query_id, _, passage_id, grade = line.split()
        qrels[query_id][passage_id] = int(grade)
    return dict(qrels)


def read_queries(path: Path) -> dict[str, str]:
    """TREC topics: query id -> query text."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        rows = (line.rstrip("\n").split("\t", 1) for line in handle if line.strip())
        return dict(rows)


def read_passages(path: Path) -> dict[str, str]:
    """The judged MS MARCO passages, extracted by `scripts/extract_judged_passages.py`."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing - run `uv run python scripts/extract_judged_passages.py` "
            "after `make data`."
        )
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        rows = (json.loads(line) for line in handle)
        return {row["id"]: row["text"] for row in rows}


def read_hotpot(path: Path) -> list[dict[str, Any]]:
    """HotpotQA's distractor validation split, as plain dictionaries."""
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing - run `make data`.")
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    return [
        {name: table.column(name)[i].as_py() for name in table.column_names}
        for i in range(table.num_rows)
    ]


# --- shared helpers ---------------------------------------------------------


def usable_text(text: str) -> bool:
    return MIN_TEXT <= len(text.strip()) <= MAX_TEXT


def assemble(
    *,
    task_id: str,
    category: Category,
    question: str,
    graded: Sequence[tuple[str, str, int, str]],
    noise_tier: NoiseTier,
    label_source: LabelSource,
    source: str,
    source_id: str,
    subcategory: str,
    gold_answer: Sequence[str],
    rationale: str,
    rng: random.Random,
    variant_of: str = "",
) -> DiscriminationTask:
    """Shuffle a graded candidate list into an item.

    `graded` is (upstream id, text, grade, title). The shuffle is what keeps
    position from carrying signal — in every source, the relevant passages
    arrive first.
    """
    order = list(graded)
    rng.shuffle(order)

    candidates = [
        Candidate(id=str(index + 1), text=text.strip(), source_id=upstream, title=title)
        for index, (upstream, text, _, title) in enumerate(order)
    ]
    relevance = {str(index + 1): grade for index, (_, _, grade, _) in enumerate(order)}
    return DiscriminationTask(
        id=task_id,
        category=category,
        question=question.strip(),
        candidates=candidates,
        relevance=relevance,
        supporting_ids=sorted((cid for cid, grade in relevance.items() if grade >= 2), key=int),
        gold_answer=list(gold_answer),
        noise_tier=noise_tier,
        label_source=label_source,
        source=source,
        source_id=source_id,
        subcategory=subcategory,
        variant_of=variant_of,
        rationale=rationale,
    )


# --- web and no_answer, from TREC Deep Learning ------------------------------

#: Rules a TREC query must pass, named so a rejection can be cited.
WEB_RULES = {
    "W1": "no candidate graded 2 or 3, so there is nothing to find",
    "W2": "fewer than four judged-irrelevant passages, so there is no noise",
    "W3": "a judged passage is missing from the extracted collection",
    "W4": "every relevant passage is outside the length bounds",
    "W5": "the query text is missing from the topics file",
    "W6": "not enough judged-irrelevant passages to fill this tier",
}

NO_ANSWER_RULES = {
    "N1": "not enough judged-irrelevant passages to fill the tier",
}


def trec_items(
    *,
    web_size: int,
    no_answer_size: int,
    seed: int,
    recorder: Recorder,
) -> tuple[list[DiscriminationTask], list[DiscriminationTask]]:
    """Build the web and no-answer categories from the TREC judgements.

    A query serves one category only. A model that had already seen the
    answerable version of a question would recognise the question rather than
    read the candidates, and the no-answer category is precisely about not
    doing that.

    Each web query is built at *every* noise tier it can fill, so the fall-off
    with candidate count can be read within a question instead of across
    different ones. Those variants are marked, and scoring must not treat them
    as independent items.
    """
    passages = read_passages(JUDGED_PASSAGES)

    pool: list[tuple[str, str, str, dict[str, int]]] = []
    for year in ("2019", "2020"):
        qrels = read_qrels(TREC / f"{year}qrels-pass.txt")
        queries = read_queries(TREC / f"msmarco-test{year}-queries.tsv.gz")
        for query_id, graded in sorted(qrels.items(), key=lambda kv: int(kv[0])):
            text = queries.get(query_id)
            if not text:
                recorder.drop("W5", WEB_RULES["W5"])
                continue
            pool.append((year, query_id, text, graded))

    # The reserve is taken from the end of the pool, deterministically, so the
    # split does not move when the sizes change.
    reserved = {entry[1] for entry in pool[-no_answer_size:]} if no_answer_size else set()

    web: list[DiscriminationTask] = []
    for year, query_id, question, graded in pool:
        if query_id in reserved or len(web) >= web_size:
            continue

        relevant = [(pid, g) for pid, g in graded.items() if g >= 2]
        irrelevant = [pid for pid, g in graded.items() if g == 0]
        if not relevant:
            recorder.drop("W1", WEB_RULES["W1"])
            continue
        if len(irrelevant) < 4:
            recorder.drop("W2", WEB_RULES["W2"])
            continue

        kept_relevant = [
            (pid, passages[pid], grade, "")
            for pid, grade in sorted(relevant, key=lambda kv: (-kv[1], kv[0]))
            if pid in passages and usable_text(passages[pid])
        ][:MAX_RELEVANT]
        if not kept_relevant:
            recorder.drop("W4", WEB_RULES["W4"])
            continue

        usable_noise = [
            pid for pid in sorted(irrelevant) if pid in passages and usable_text(passages[pid])
        ]
        if len(usable_noise) < 2:
            recorder.drop("W3", WEB_RULES["W3"])
            continue

        first_id = ""
        for tier, size in TIER_SIZES.items():
            if len(web) >= web_size:
                break
            rng = random.Random(f"{seed}-web-{query_id}-{tier}")
            # Noise dominates every tier: one relevant passage in five, two in
            # ten, four in twenty. A set that is mostly relevant measures
            # reading comprehension, not discrimination.
            relevant_here = kept_relevant[: max(1, min(len(kept_relevant), size // 4))]
            wanted_noise = size - len(relevant_here)
            if len(usable_noise) < wanted_noise:
                recorder.drop("W6", WEB_RULES["W6"])
                continue

            noise = list(usable_noise)
            rng.shuffle(noise)
            task_id = f"srd-web-dl{year[2:]}-{query_id}-{tier}"
            web.append(
                assemble(
                    task_id=task_id,
                    category=Category.WEB,
                    question=question,
                    graded=relevant_here
                    + [(pid, passages[pid], 0, "") for pid in noise[:wanted_noise]],
                    noise_tier=tier,
                    label_source=LabelSource.HUMAN,
                    source=f"trec-dl-{year}",
                    source_id=query_id,
                    subcategory=f"dl{year[2:]}",
                    gold_answer=[],
                    rationale=(
                        "TREC assessors graded every candidate against this query; the "
                        "irrelevant ones were retrieved for it, so they are on topic "
                        "without answering it."
                    ),
                    rng=rng,
                    variant_of=first_id,
                )
            )
            first_id = first_id or task_id

    no_answer: list[DiscriminationTask] = []
    tiers = list(TIER_SIZES)
    for index, (year, query_id, question, graded) in enumerate(pool):
        if query_id not in reserved or len(no_answer) >= no_answer_size:
            continue
        rng = random.Random(f"{seed}-none-{query_id}")
        tier = tiers[index % len(tiers)]
        size = TIER_SIZES[tier]

        # Grade 1 is "related but does not answer", which is exactly the grey
        # area this category is not about. Only outright zeroes go in.
        zeroes = [
            pid
            for pid in sorted(pid for pid, g in graded.items() if g == 0)
            if pid in passages and usable_text(passages[pid])
        ]
        if len(zeroes) < size:
            recorder.drop("N1", NO_ANSWER_RULES["N1"])
            continue
        rng.shuffle(zeroes)
        no_answer.append(
            assemble(
                task_id=f"srd-none-dl{year[2:]}-{query_id}",
                category=Category.NO_ANSWER,
                question=question,
                graded=[(pid, passages[pid], 0, "") for pid in zeroes[:size]],
                noise_tier=tier,
                label_source=LabelSource.HUMAN,
                source=f"trec-dl-{year}",
                source_id=query_id,
                subcategory=f"dl{year[2:]}-no-answer",
                gold_answer=[],
                rationale=(
                    "Every candidate here was read by a TREC assessor against this "
                    "query and graded 0. The right response is that the results do "
                    "not answer it."
                ),
                rng=rng,
            )
        )

    return web, no_answer


# --- wikipedia, from HotpotQA distractor -------------------------------------

HOTPOT_RULES = {
    "H1": "not the ten-paragraph distractor layout",
    "H2": "a yes/no answer, which needs no evidence to guess",
    "H3": "a supporting title is missing from the paragraph list",
    "H4": "the answer does not appear in either supporting paragraph",
    "H5": "a paragraph is outside the length bounds",
    "H6": "not enough borrowed distractors for the hard tier",
}


def paragraphs(context: dict[str, Any]) -> list[tuple[str, str]]:
    """HotpotQA context as (title, joined sentences)."""
    titles = list(context.get("title") or [])
    sentences = list(context.get("sentences") or [])
    return [
        (str(title), "".join(str(part) for part in parts).strip())
        for title, parts in zip(titles, sentences, strict=False)
    ]


def hotpot_items(*, size: int, seed: int, recorder: Recorder) -> list[DiscriminationTask]:
    """Build the Wikipedia category from HotpotQA's distractor split."""
    rows = read_hotpot(HOTPOT)

    prepared: list[tuple[dict[str, Any], list[tuple[str, str]], set[str]]] = []
    for row in rows:
        answer = str(row["answer"]).strip()
        if answer.lower() in {"yes", "no"}:
            recorder.drop("H2", HOTPOT_RULES["H2"])
            continue

        paras = paragraphs(row["context"])
        if len(paras) != 10:
            recorder.drop("H1", HOTPOT_RULES["H1"])
            continue

        facts = row["supporting_facts"] or {}
        gold_titles = {str(title) for title in facts.get("title", [])}
        by_title = dict(paras)
        if not gold_titles or any(title not in by_title for title in gold_titles):
            recorder.drop("H3", HOTPOT_RULES["H3"])
            continue
        if not any(answer.lower() in by_title[title].lower() for title in gold_titles):
            recorder.drop("H4", HOTPOT_RULES["H4"])
            continue
        if any(not usable_text(text) for _, text in paras):
            recorder.drop("H5", HOTPOT_RULES["H5"])
            continue

        prepared.append((row, paras, gold_titles))

    # A spare pool of other questions' distractors, for the hard tier. They are
    # HotpotQA paragraphs either way; borrowing only changes which question
    # they were a distractor for.
    spare = [
        (title, text)
        for _, paras, gold in prepared
        for title, text in paras
        if title not in gold
    ]

    chooser = random.Random(f"{seed}-hotpot-order")
    chooser.shuffle(prepared)

    tiers = list(TIER_SIZES)
    items: list[DiscriminationTask] = []
    for index, (row, paras, gold_titles) in enumerate(prepared):
        if len(items) >= size:
            break
        answer = str(row["answer"]).strip()
        source_id = str(row["id"])
        rng = random.Random(f"{seed}-wiki-{source_id}")
        tier = tiers[index % len(tiers)]
        target = TIER_SIZES[tier]

        gold = [(title, text) for title, text in paras if title in gold_titles]
        distractors = [(title, text) for title, text in paras if title not in gold_titles]
        rng.shuffle(distractors)

        chosen = distractors[: max(target - len(gold), 0)]
        if target > len(paras):
            # Hard tier: top up from other questions, skipping anything that
            # shares a title with the gold paragraphs or happens to contain the
            # answer, either of which would make a "distractor" relevant.
            borrowed: list[tuple[str, str]] = []
            pool = list(spare)
            rng.shuffle(pool)
            for title, text in pool:
                if len(gold) + len(chosen) + len(borrowed) >= target:
                    break
                if title in gold_titles or answer.lower() in text.lower():
                    continue
                if any(title == existing for existing, _ in chosen + borrowed):
                    continue
                borrowed.append((title, text))
            if len(gold) + len(chosen) + len(borrowed) < target:
                recorder.drop("H6", HOTPOT_RULES["H6"])
                continue
            chosen = chosen + borrowed

        graded = [(f"{title}", text, 3, title) for title, text in gold] + [
            (f"{title}", text, 0, title) for title, text in chosen
        ]

        items.append(
            assemble(
                task_id=f"srd-wiki-{source_id[:12]}",
                category=Category.WIKIPEDIA,
                question=str(row["question"]),
                graded=graded,
                noise_tier=tier,
                label_source=LabelSource.DERIVED,
                source="hotpotqa",
                source_id=source_id,
                subcategory=f"{row['type']}-{row['level']}",
                gold_answer=[answer],
                rationale=(
                    "HotpotQA marks which paragraphs its supporting sentences came "
                    "from; those are graded 3 and the rest 0. The grade is inferred "
                    "from the dataset's structure, not a relevance judgement."
                ),
                rng=rng,
            )
        )

    return items


# --- build ------------------------------------------------------------------


def build(
    *,
    seed: int = DEFAULT_SEED,
    web_size: int = DEFAULT_WEB,
    no_answer_size: int = DEFAULT_NO_ANSWER,
    wikipedia_size: int = DEFAULT_WIKIPEDIA,
) -> tuple[list[DiscriminationTask], BuildReport]:
    """Build the whole task set, with a report of what was turned away."""
    recorder = Recorder()

    web, no_answer = trec_items(
        web_size=web_size, no_answer_size=no_answer_size, seed=seed, recorder=recorder
    )
    wikipedia = hotpot_items(size=wikipedia_size, seed=seed, recorder=recorder)

    items = web + wikipedia + no_answer
    report = BuildReport(
        seed=seed,
        counts={
            "total": len(items),
            Category.WEB: len(web),
            Category.WIKIPEDIA: len(wikipedia),
            Category.NO_ANSWER: len(no_answer),
        },
        tiers=dict(collections.Counter(str(item.noise_tier) for item in items)),
        label_sources=dict(collections.Counter(str(item.label_source) for item in items)),
        candidates_total=sum(item.candidate_count for item in items),
        relevant_total=sum(item.relevant_count for item in items),
        dropped=recorder.rejections(),
        notes=[
            "Every model sees the same candidates in the same order; the order is a "
            "seeded shuffle, so position carries no signal.",
            "TREC grades are human relevance judgements. HotpotQA grades are derived "
            "from its supporting facts and only ever 0 or 3.",
            "The web category has no gold answer: TREC judged relevance, not answers. "
            "Answer correctness is scored on the wikipedia category only.",
        ],
    )
    return items, report


#: Sources whose text this repository may not redistribute. Microsoft grants
#: non-commercial research use of MS MARCO and extends no licence, so items
#: built from it stay on the machine that built them; their ids and checksums
#: are committed instead, which is enough to verify a local build.
WITHHELD_SOURCES = ("trec-dl",)


def withheld(item: DiscriminationTask) -> bool:
    return item.source.startswith(WITHHELD_SOURCES)


def fingerprint(item: DiscriminationTask) -> str:
    """A checksum of one item, so a local build can be checked against ours."""
    canonical = json.dumps(item.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save(items: Sequence[DiscriminationTask], path: Path) -> dict[str, Path]:
    """Write the task set, splitting off what cannot be redistributed.

    Returns the paths written. The shippable items go to `path`; the rest go
    beside it under `local/`, which is git-ignored, together with a manifest of
    ids and checksums that *is* committed.
    """
    shippable = [item for item in items if not withheld(item)]
    local = [item for item in items if withheld(item)]

    path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(path, [item.model_dump(mode="json") for item in shippable])
    written = {"shipped": path}

    if local:
        local_path = path.parent / "local" / f"{path.stem}-local.jsonl"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(local_path, [item.model_dump(mode="json") for item in local])
        written["local"] = local_path

        manifest = path.with_suffix(".local.manifest.json")
        manifest.write_text(
            json.dumps(
                {
                    "note": (
                        "These items are built locally because their passage text "
                        "comes from MS MARCO, whose terms grant non-commercial "
                        "research use and extend no licence. Rebuild them with "
                        "`llmsearchbench tasks build-discrimination` after `make data` "
                        "and `scripts/extract_judged_passages.py`; the checksums below "
                        "prove your build matches the published one."
                    ),
                    "seed": DEFAULT_SEED,
                    "count": len(local),
                    "items": {
                        item.id: fingerprint(item) for item in sorted(local, key=lambda i: i.id)
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        written["manifest"] = manifest

    return written
