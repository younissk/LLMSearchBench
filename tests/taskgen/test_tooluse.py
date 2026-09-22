"""Building the tool-use-correctness task set."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from llmsearchbench.paths import TASKS
from llmsearchbench.storage import read_jsonl
from llmsearchbench.taskgen.tooluse import RETRIEVALQA, build
from llmsearchbench.types.tooluse import Bucket, ToolUseTask

TASK_SET = TASKS / "tool-use-correctness.jsonl"
REPORT = TASKS / "tool-use-correctness.report.json"

needs_source = pytest.mark.skipif(
    not RETRIEVALQA.exists(), reason="source data not fetched; run `make data`"
)


@pytest.fixture(scope="module")
def committed() -> list[ToolUseTask]:
    return [ToolUseTask.model_validate(raw) for raw in read_jsonl(TASK_SET)]


class TestCommittedSet:
    def test_every_item_parses(self, committed: list[ToolUseTask]) -> None:
        assert committed

    def test_ids_are_unique(self, committed: list[ToolUseTask]) -> None:
        ids = [task.id for task in committed]
        assert len(ids) == len(set(ids))

    def test_prompts_are_unique(self, committed: list[ToolUseTask]) -> None:
        """A repeated prompt would be scored twice and weight one item double."""
        prompts = [task.prompt for task in committed]
        assert len(prompts) == len(set(prompts))

    def test_all_three_buckets_are_populated(self, committed: list[ToolUseTask]) -> None:
        present = {task.bucket for task in committed}
        assert present == set(Bucket)

    def test_only_the_search_bucket_expects_a_search(
        self, committed: list[ToolUseTask]
    ) -> None:
        for task in committed:
            assert task.expects_search == (task.bucket is Bucket.SEARCH)

    def test_no_tool_items_carry_no_gold_answer(self, committed: list[ToolUseTask]) -> None:
        for task in committed:
            if task.bucket is Bucket.NO_TOOL:
                assert task.gold_answer == []
            else:
                assert task.gold_answer

    def test_no_time_dependent_prompt_survived(self, committed: list[ToolUseTask]) -> None:
        """A 2023 gold answer to `how old is X` is simply wrong now."""
        expires = re.compile(
            r"\b(latest|most recent|currently|present|nowadays|how old is|richest)\b",
            re.IGNORECASE,
        )
        offenders = [
            task.id
            for task in committed
            if task.bucket is not Bucket.NO_TOOL and expires.search(task.prompt)
        ]
        assert offenders == []

    def test_adversarial_items_exist_and_are_no_tool(
        self, committed: list[ToolUseTask]
    ) -> None:
        adversarial = [task for task in committed if task.adversarial]
        assert len(adversarial) >= 10
        assert all(task.bucket is Bucket.NO_TOOL for task in adversarial)

    def test_the_committed_report_matches_the_committed_set(
        self, committed: list[ToolUseTask]
    ) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        assert sum(report["selected"].values()) == len(committed)


@needs_source
class TestBuild:
    def test_is_deterministic(self) -> None:
        """A seeded rebuild has to reproduce the committed set exactly."""
        first, _ = build()
        second, _ = build()
        assert [t.model_dump() for t in first] == [t.model_dump() for t in second]

    def test_reproduces_the_committed_file(self, committed: list[ToolUseTask]) -> None:
        rebuilt, _ = build()
        assert [t.model_dump() for t in rebuilt] == [t.model_dump() for t in committed]

    def test_a_different_seed_changes_the_sample(self) -> None:
        default, _ = build()
        other, _ = build(seed=1)
        assert [t.id for t in default] != [t.id for t in other]

    def test_report_accounts_for_every_dropped_candidate(self) -> None:
        _, report = build()
        for bucket in ("memory", "search"):
            assert report.eligible[bucket] >= report.selected[bucket]
            assert sum(report.dropped[bucket].values()) > 0

    def test_sizes_are_respected(self) -> None:
        tasks, _ = build(memory_size=10, search_size=15)
        assert sum(1 for t in tasks if t.bucket is Bucket.MEMORY) == 10
        assert sum(1 for t in tasks if t.bucket is Bucket.SEARCH) == 15

    def test_no_source_dominates_the_search_bucket(self) -> None:
        """PopQA is 52% of the retrieval-required source and one question template."""
        tasks, _ = build()
        search = [t for t in tasks if t.bucket is Bucket.SEARCH]
        popqa = sum(1 for t in search if t.subcategory == "popqa")
        assert popqa / len(search) < 0.5

    def test_missing_source_data_says_how_to_fetch_it(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "llmsearchbench.taskgen.tooluse.RETRIEVALQA", tmp_path / "absent.jsonl"
        )
        with pytest.raises(FileNotFoundError, match="make data"):
            build()
