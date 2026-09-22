"""The run loop, driven by fakes so it never touches a network."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from llmsearchbench.harness import (
    BackendNotConfiguredError,
    Document,
    EchoAdapter,
    HarnessConfig,
    Judgement,
    ModelAnswer,
    NotConfiguredError,
    RecordingBackend,
    SearchBackend,
    StaticBackend,
    build_adapter,
    build_backend,
    run_task,
    run_tasks,
)
from llmsearchbench.providers import UnknownModelError
from llmsearchbench.storage import load_records
from llmsearchbench.types import Task, Verdict

CORPUS = [
    Document(
        url="https://example.org/a",
        title="Widget registry",
        text="Ada Lovelace maintains the registry.",
    ),
    Document(
        url="https://example.org/b",
        title="Registry history",
        text="The registry began in 1843.",
    ),
    Document(
        url="https://example.org/c",
        title="Acme news",
        text="Acme acquired the registry in 2024.",
    ),
]


class SearchingAdapter:
    """Searches once, cites everything it saw, and reports fixed token counts."""

    def __init__(self, searches: int = 1) -> None:
        self.searches = searches

    def answer(self, task: Task, backend: SearchBackend, config: HarnessConfig) -> ModelAnswer:
        seen: list[Document] = []
        for _ in range(min(self.searches, config.max_calls)):
            seen.extend(backend.search(task.question, config.top_k))
        return ModelAnswer(
            answer="Ada Lovelace",
            citations=[doc.url for doc in seen],
            tokens_in=1000,
            tokens_out=100,
            latency_s=1.5,
            search_calls=min(self.searches, config.max_calls),
        )


class AlwaysCorrectJudge:
    def judge(
        self, task: Task, answer: ModelAnswer, retrieved: Sequence[Document]
    ) -> Judgement:
        return Judgement(verdict=Verdict.CORRECT, unsupported_claims=0, total_claims=2)


class TestRecordingBackend:
    def test_keeps_every_document_for_the_judge(self) -> None:
        """The judge rules on support, so it needs what the model actually saw."""
        recorder = RecordingBackend(StaticBackend(CORPUS))
        recorder.search("registry", top_k=2)
        recorder.search("Acme", top_k=2)
        assert len(recorder.retrieved) > 0
        assert all(isinstance(doc, Document) for doc in recorder.retrieved)

    def test_passes_results_through_unchanged(self) -> None:
        inner = StaticBackend(CORPUS)
        recorder = RecordingBackend(inner)
        assert list(recorder.search("Acme", 5)) == list(inner.search("Acme", 5))


class TestStaticBackend:
    def test_returns_matching_documents(self) -> None:
        hits = StaticBackend(CORPUS).search("Acme", top_k=5)
        assert [doc.url for doc in hits] == ["https://example.org/c"]

    def test_respects_top_k(self) -> None:
        assert len(StaticBackend(CORPUS).search("registry", top_k=1)) == 1

    def test_no_match_returns_nothing(self) -> None:
        assert StaticBackend(CORPUS).search("quantum", top_k=5) == []


class TestRunTask:
    def test_produces_a_record_carrying_the_judgement(self, tasks: list[Task]) -> None:
        record = run_task(
            tasks[0],
            "test-model",
            SearchingAdapter(),
            StaticBackend(CORPUS),
            AlwaysCorrectJudge(),
            HarnessConfig(),
        )
        assert record.task_id == "t-001"
        assert record.model == "test-model"
        assert record.verdict is Verdict.CORRECT
        assert record.total_claims == 2

    def test_max_calls_caps_the_search_budget(self, tasks: list[Task]) -> None:
        """A model that would search forever must be stopped by the harness, not trusted."""
        record = run_task(
            tasks[0],
            "test-model",
            SearchingAdapter(searches=50),
            StaticBackend(CORPUS),
            AlwaysCorrectJudge(),
            HarnessConfig(max_calls=3),
        )
        assert record.search_calls == 3

    def test_a_model_that_never_searches_is_still_recorded(self, tasks: list[Task]) -> None:
        record = run_task(
            tasks[0],
            "echo",
            EchoAdapter(),
            StaticBackend(CORPUS),
            AlwaysCorrectJudge(),
            HarnessConfig(),
        )
        assert record.search_calls == 0
        assert record.citations == []


class TestRunTasks:
    def test_runs_every_task(self, tasks: list[Task]) -> None:
        records = run_tasks(
            tasks,
            "test-model",
            SearchingAdapter(),
            StaticBackend(CORPUS),
            AlwaysCorrectJudge(),
            HarnessConfig(),
        )
        assert [r.task_id for r in records] == ["t-001", "t-002", "t-003"]

    def test_appends_as_it_goes_so_a_crash_keeps_earlier_work(
        self, tasks: list[Task], tmp_path: Path
    ) -> None:
        raw = tmp_path / "raw.jsonl"

        class FailsOnThirdTask(SearchingAdapter):
            def __init__(self) -> None:
                super().__init__()
                self.seen = 0

            def answer(
                self, task: Task, backend: SearchBackend, config: HarnessConfig
            ) -> ModelAnswer:
                self.seen += 1
                if self.seen == 3:
                    raise RuntimeError("provider timed out")
                return super().answer(task, backend, config)

        with pytest.raises(RuntimeError, match="timed out"):
            run_tasks(
                tasks,
                "test-model",
                FailsOnThirdTask(),
                StaticBackend(CORPUS),
                AlwaysCorrectJudge(),
                HarnessConfig(),
                raw_path=raw,
            )

        assert [r.task_id for r in load_records(raw)] == ["t-001", "t-002"]

    def test_without_a_path_nothing_is_written(self, tasks: list[Task], tmp_path: Path) -> None:
        run_tasks(
            tasks,
            "test-model",
            SearchingAdapter(),
            StaticBackend(CORPUS),
            AlwaysCorrectJudge(),
            HarnessConfig(),
        )
        assert list(tmp_path.iterdir()) == []


class TestWiring:
    def test_an_unknown_backend_names_the_ones_that_exist(self) -> None:
        """Silently falling back to a different backend would void the comparison."""
        with pytest.raises(BackendNotConfiguredError, match="unknown search backend"):
            build_backend("some-search-api")

    def test_a_backend_with_no_key_says_which_variable_to_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        with pytest.raises(BackendNotConfiguredError, match="TAVILY_API_KEY"):
            build_backend("tavily")

    def test_a_model_with_no_key_says_which_variable_to_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(NotConfiguredError, match="ANTHROPIC_API_KEY"):
            build_adapter("claude-opus-5")

    def test_a_model_outside_the_catalogue_fails_first(self) -> None:
        """A typo should name the catalogue, not send you hunting for a key."""
        with pytest.raises(UnknownModelError, match="unknown model"):
            build_adapter("not-a-real-model")
