"""On-disk artefacts: the round trip, and the failure modes that lose a run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from llmsearchbench.storage import (
    append_record,
    load_records,
    load_tasks,
    read_jsonl,
    write_jsonl,
)
from llmsearchbench.types import Category, Task
from tests.conftest import make_record


class TestJsonl:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "rows.jsonl"
        rows = [{"a": 1}, {"a": 2}]
        write_jsonl(path, rows)
        assert list(read_jsonl(path)) == rows

    def test_blank_lines_are_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "rows.jsonl"
        path.write_text('{"a": 1}\n\n   \n{"a": 2}\n', encoding="utf-8")
        assert list(read_jsonl(path)) == [{"a": 1}, {"a": 2}]

    def test_a_corrupt_line_names_the_line_number(self, tmp_path: Path) -> None:
        """A half-written line from an interrupted run must not be a silent skip."""
        path = tmp_path / "rows.jsonl"
        path.write_text('{"a": 1}\n{"a": \n', encoding="utf-8")
        with pytest.raises(ValueError, match=r":2:"):
            list(read_jsonl(path))

    def test_unicode_survives_the_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "rows.jsonl"
        text = "Ada Lovelace \u2014 1843 \u00b7 na\u00efve"
        write_jsonl(path, [{"answer": text}])
        assert next(iter(read_jsonl(path)))["answer"] == text


class TestRecords:
    def test_append_keeps_earlier_records(self, tmp_path: Path) -> None:
        """An interrupted run must keep everything it already paid for."""
        path = tmp_path / "raw.jsonl"
        append_record(path, make_record("t-001"))
        append_record(path, make_record("t-002"))
        assert [r.task_id for r in load_records(path)] == ["t-001", "t-002"]

    def test_append_creates_the_directory(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "raw.jsonl"
        append_record(path, make_record())
        assert path.exists()

    def test_record_round_trip_preserves_every_field(self, tmp_path: Path) -> None:
        path = tmp_path / "raw.jsonl"
        original = make_record(
            "t-042", citations=["https://x.example"], unsupported_claims=2, total_claims=7
        )
        append_record(path, original)
        assert load_records(path) == [original]

    def test_claim_counts_default_when_absent(self, tmp_path: Path) -> None:
        """Older runs predate per-claim support and must still load."""
        path = tmp_path / "raw.jsonl"
        path.write_text(
            json.dumps(
                {
                    "task_id": "t-001",
                    "model": "m",
                    "answer": "a",
                    "citations": [],
                    "verdict": "correct",
                    "tokens_in": 1,
                    "tokens_out": 1,
                    "latency_s": 1.0,
                    "search_calls": 1,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert load_records(path)[0].total_claims == 0


class TestTasks:
    def test_load_tasks(self, tmp_path: Path) -> None:
        path = tmp_path / "v0.1.0.jsonl"
        write_jsonl(
            path,
            [
                {
                    "id": "t-001",
                    "question": "q",
                    "gold_answer": "a",
                    "gold_sources": ["https://example.org/a"],
                    "category": "single-hop",
                    "freshness_cutoff": "2026-01-01",
                }
            ],
        )
        assert load_tasks(path) == [
            Task(
                id="t-001",
                question="q",
                gold_answer="a",
                gold_sources=["https://example.org/a"],
                category=Category.SINGLE_HOP,
                freshness_cutoff="2026-01-01",
            )
        ]

    def test_a_task_missing_gold_sources_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "v0.1.0.jsonl"
        write_jsonl(
            path,
            [{"id": "t-001", "question": "q", "gold_answer": "a", "category": "single-hop"}],
        )
        with pytest.raises(ValidationError, match="gold_sources"):
            load_tasks(path)

    def test_an_unknown_category_is_rejected(self, tmp_path: Path) -> None:
        """Categories are a closed set; a new one changes the task-set proportions."""
        path = tmp_path / "v0.1.0.jsonl"
        write_jsonl(
            path,
            [
                {
                    "id": "t-001",
                    "question": "q",
                    "gold_answer": "a",
                    "gold_sources": [],
                    "category": "trick-question",
                }
            ],
        )
        with pytest.raises(ValidationError, match="category"):
            load_tasks(path)


class TestLoadAttempts:
    def test_reads_current_attempts(self, tmp_path: Path) -> None:
        from llmsearchbench.storage import load_attempts
        from llmsearchbench.types.tooluse import ToolUseAttempt

        path = tmp_path / "attempts.jsonl"
        attempt = ToolUseAttempt(task_id="t1", model="m", answer="hi")
        path.write_text(attempt.model_dump_json() + "\n", encoding="utf-8")
        assert load_attempts(path) == [attempt]

    def test_tolerates_a_field_that_has_since_been_removed(self, tmp_path: Path) -> None:
        """Attempts files cost real money; removing a field must not orphan them."""
        from llmsearchbench.storage import load_attempts

        path = tmp_path / "attempts.jsonl"
        path.write_text(
            json.dumps({"task_id": "t1", "model": "m", "answer": "hi", "turns": 2}) + "\n",
            encoding="utf-8",
        )
        assert load_attempts(path)[0].task_id == "t1"

    def test_a_genuinely_unknown_field_still_fails(self, tmp_path: Path) -> None:
        """The legacy list is explicit, so a typo is still caught."""
        from pydantic import ValidationError

        from llmsearchbench.storage import load_attempts

        path = tmp_path / "attempts.jsonl"
        path.write_text(
            json.dumps({"task_id": "t1", "model": "m", "tokens_ni": 5}) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="tokens_ni"):
            load_attempts(path)
