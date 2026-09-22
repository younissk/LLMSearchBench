"""The tool-use run loop, driven by a fake Messages API. No network, no keys."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from llmsearchbench.harness.adapters import AnthropicAdapter, validate_search_arguments
from llmsearchbench.harness.config import HarnessConfig
from llmsearchbench.harness.protocols import Document
from llmsearchbench.harness.tooluse import completed_task_ids, run_tasks
from llmsearchbench.providers import get_model
from llmsearchbench.types.tooluse import Bucket, ToolUseTask


class Block:
    def __init__(self, **fields: Any) -> None:
        self.__dict__.update(fields)


class Usage:
    def __init__(self, input_tokens: int = 100, output_tokens: int = 50) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class Response:
    def __init__(self, stop_reason: str, content: list[Block]) -> None:
        self.stop_reason = stop_reason
        self.content = content
        self.usage = Usage()


class FakeMessages:
    """Replays a scripted list of responses and records every request."""

    def __init__(self, script: list[Response]) -> None:
        self._script = list(script)
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> Response:
        self.requests.append(request)
        if not self._script:
            return Response("end_turn", [Block(type="text", text="done")])
        return self._script.pop(0)


def adapter_for(script: list[Response], model_id: str = "claude-opus-5") -> AnthropicAdapter:
    adapter = AnthropicAdapter.__new__(AnthropicAdapter)
    adapter._spec = get_model(model_id)  # type: ignore[attr-defined]
    adapter._effort = "high"  # type: ignore[attr-defined]
    adapter._client = Block(messages=FakeMessages(script))  # type: ignore[attr-defined]
    return adapter


class StubBackend:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, top_k: int) -> Sequence[Document]:
        self.queries.append(query)
        return [Document(url="https://example.invalid/a", title="A", text="an answer")]


def task(task_id: str = "t1", bucket: Bucket = Bucket.SEARCH) -> ToolUseTask:
    return ToolUseTask(
        id=task_id,
        bucket=bucket,
        prompt="a prompt",
        gold_answer=[] if bucket is Bucket.NO_TOOL else ["an answer"],
        source="test",
        subcategory="test",
    )


def answered(text: str = "an answer") -> Response:
    return Response("end_turn", [Block(type="text", text=text)])


def searched(query: Any = "a query", name: str = "search") -> Response:
    return Response(
        "tool_use",
        [Block(type="tool_use", id="tu_1", name=name, input={"query": query})],
    )


class TestValidateSearchArguments:
    def test_accepts_a_good_call(self) -> None:
        assert validate_search_arguments({"query": "who?"}) == ({"query": "who?"}, None)

    def test_reports_a_missing_query(self) -> None:
        _, error = validate_search_arguments({})
        assert error is not None and "query" in error

    def test_reports_an_unexpected_argument(self) -> None:
        _, error = validate_search_arguments({"query": "x", "limit": "3"})
        assert error is not None and "limit" in error

    def test_reports_a_non_object(self) -> None:
        _, error = validate_search_arguments("just a string")
        assert error is not None and "object" in error


class TestAdapter:
    def test_an_answer_without_a_search_records_no_calls(self) -> None:
        adapter = adapter_for([answered()])
        turn = adapter.answer("prompt", StubBackend(), HarnessConfig())
        assert turn.answer == "an answer"
        assert turn.calls == []
        assert turn.tokens_in == 100 and turn.tokens_out == 50
        assert turn.latency_s >= 0
        assert turn.turns == 1
        assert turn.stop_reason == "end_turn"

    def test_a_search_is_executed_and_recorded(self) -> None:
        backend = StubBackend()
        adapter = adapter_for([searched("sleep divorce"), answered()])
        turn = adapter.answer("prompt", backend, HarnessConfig())
        assert [call.query for call in turn.calls] == ["sleep divorce"]
        assert backend.queries == ["sleep divorce"]

    def test_tokens_accumulate_across_turns(self) -> None:
        adapter = adapter_for([searched(), answered()])
        turn = adapter.answer("prompt", StubBackend(), HarnessConfig())
        assert turn.tokens_in == 200 and turn.tokens_out == 100
        assert turn.turns == 2, "a search costs a second round trip"

    def test_a_malformed_call_is_recorded_and_the_model_gets_a_chance_to_recover(
        self,
    ) -> None:
        """A bad call is data, not an exception - the run must continue."""
        adapter = adapter_for(
            [
                Response(
                    "tool_use",
                    [Block(type="tool_use", id="tu_1", name="search", input={})],
                ),
                answered(),
            ]
        )
        turn = adapter.answer("prompt", StubBackend(), HarnessConfig())
        assert turn.calls[0].schema_error is not None
        assert "query" in turn.calls[0].schema_error

    def test_a_wrong_tool_is_recorded_and_not_executed(self) -> None:
        backend = StubBackend()
        adapter = adapter_for([searched(name="calculator"), answered()])
        turn = adapter.answer("prompt", backend, HarnessConfig())
        assert turn.calls[0].name == "calculator"
        assert backend.queries == []

    def test_an_empty_query_is_not_sent_to_the_backend(self) -> None:
        backend = StubBackend()
        adapter = adapter_for([searched(query="   "), answered()])
        adapter.answer("prompt", backend, HarnessConfig())
        assert backend.queries == []

    def test_a_model_that_never_stops_is_cut_off_past_the_budget(self) -> None:
        """Over-budget has to be observable, so the loop runs one turn past it."""
        adapter = adapter_for([searched(f"q{i}") for i in range(12)])
        turn = adapter.answer("prompt", StubBackend(), HarnessConfig(max_calls=3))
        assert len(turn.calls) > 3

    def test_sampling_is_omitted_for_models_that_reject_it(self) -> None:
        """Opus 5 and Sonnet 5 return 400 when temperature is sent."""
        adapter = adapter_for([answered()], model_id="claude-opus-5")
        adapter.answer("prompt", StubBackend(), HarnessConfig())
        assert "temperature" not in adapter._client.messages.requests[0]  # type: ignore[attr-defined]

    def test_sampling_is_sent_for_models_that_accept_it(self) -> None:
        adapter = adapter_for([answered()], model_id="claude-haiku-4-5")
        adapter.answer("prompt", StubBackend(), HarnessConfig())
        assert "temperature" in adapter._client.messages.requests[0]  # type: ignore[attr-defined]

    def test_the_search_tool_is_not_strict(self) -> None:
        """Strict mode would make malformed calls impossible to observe."""
        adapter = adapter_for([answered()])
        adapter.answer("prompt", StubBackend(), HarnessConfig())
        tool = adapter._client.messages.requests[0]["tools"][0]  # type: ignore[attr-defined]
        assert "strict" not in tool


class TestRunTasks:
    def test_writes_each_attempt_as_it_lands(self, tmp_path: Path) -> None:
        out = tmp_path / "attempts.jsonl"
        adapter = adapter_for([answered(), answered(), answered()])
        run_tasks(
            [task("a"), task("b"), task("c")],
            "claude-opus-5",
            adapter,
            StubBackend(),
            HarnessConfig(),
            out_path=out,
        )
        assert completed_task_ids(out) == {"a", "b", "c"}

    def test_an_interrupted_run_keeps_what_it_paid_for(self, tmp_path: Path) -> None:
        out = tmp_path / "attempts.jsonl"

        class Exploding(FakeMessages):
            def create(self, **request: Any) -> Response:
                if len(self.requests) >= 1:
                    raise ConnectionError("the provider went away")
                return super().create(**request)

        adapter = adapter_for([])
        adapter._client = Block(messages=Exploding([answered(), answered()]))  # type: ignore[attr-defined]

        with pytest.raises(ConnectionError):
            run_tasks(
                [task("a"), task("b"), task("c")],
                "claude-opus-5",
                adapter,
                StubBackend(),
                HarnessConfig(),
                out_path=out,
            )
        assert completed_task_ids(out) == {"a"}

    def test_completed_ids_is_empty_when_nothing_has_run(self, tmp_path: Path) -> None:
        assert completed_task_ids(tmp_path / "absent.jsonl") == set()
