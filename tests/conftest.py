"""Shared fixtures.

The records here are hand-built rather than loaded from a file so a test that
breaks points at the behaviour, not at a fixture nobody reads.
"""

from __future__ import annotations

import pytest

from llmsearchbench.types import Category, ResultRow, RunRecord, Summary, Task, Verdict


@pytest.fixture
def tasks() -> list[Task]:
    return [
        Task(
            id="t-001",
            question="Who maintains the widget registry?",
            gold_answer="Ada Lovelace",
            gold_sources=["https://example.org/a", "https://example.org/b"],
            category=Category.SINGLE_HOP,
        ),
        Task(
            id="t-002",
            question="Which company acquired the registry, and when?",
            gold_answer="Acme, 2024",
            gold_sources=["https://example.org/c"],
            category=Category.MULTI_HOP,
        ),
        Task(
            id="t-003",
            question="Did the registry ever ship a quantum backend?",
            gold_answer="No reliable source says so.",
            gold_sources=[],
            category=Category.NEGATIVE,
        ),
    ]


def make_record(
    task_id: str = "t-001",
    model: str = "test-model",
    *,
    verdict: Verdict = Verdict.CORRECT,
    citations: list[str] | None = None,
    tokens_in: int = 10_000,
    tokens_out: int = 500,
    latency_s: float = 5.0,
    search_calls: int = 2,
    unsupported_claims: int = 0,
    total_claims: int = 4,
) -> RunRecord:
    return RunRecord(
        task_id=task_id,
        model=model,
        answer="an answer",
        citations=citations if citations is not None else ["https://example.org/a"],
        verdict=verdict,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_s=latency_s,
        search_calls=search_calls,
        unsupported_claims=unsupported_claims,
        total_claims=total_claims,
    )


@pytest.fixture
def records() -> list[RunRecord]:
    return [
        make_record("t-001", verdict=Verdict.CORRECT, latency_s=4.0),
        make_record("t-002", verdict=Verdict.INCORRECT, latency_s=6.0, citations=[]),
        make_record("t-003", verdict=Verdict.CORRECT, latency_s=8.0, citations=[]),
    ]


@pytest.fixture
def gold_sources(tasks: list[Task]) -> dict[str, list[str]]:
    return {task.id: task.gold_sources for task in tasks}


def make_row(model: str = "test-model", **overrides: float | str) -> ResultRow:
    values: dict[str, object] = {
        "model": model,
        "provider": "Test Provider",
        "accuracy": 0.80,
        "citation_f1": 0.70,
        "hallucination_rate": 0.06,
        "latency_p50": 6.0,
        "cost_per_1k": 12.0,
        "search_calls": 3.0,
    }
    values.update(overrides)
    return ResultRow.model_validate(values)


def make_summary(*rows: ResultRow, version: str = "v0.1.0") -> Summary:
    return Summary(
        version=version,
        date="2026-09-22",
        task_count=120,
        rows=list(rows) or [make_row()],
    )
