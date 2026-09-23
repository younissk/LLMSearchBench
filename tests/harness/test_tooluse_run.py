"""The run loop, driven by a fake API. No network, no keys, no search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from llmsearchbench.harness.adapters import AnthropicAdapter, validate_search_arguments
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
    def test_an_answer_without_a_search(self) -> None:
        turn = adapter_for([answered()]).answer("prompt")
        assert turn.answer == "an answer"
        assert turn.calls == []
        assert not turn.searched
        assert turn.tokens_in == 100 and turn.tokens_out == 50

    def test_a_search_is_recorded_and_the_episode_ends(self) -> None:
        """The decision is the measurement; nothing is executed."""
        adapter = adapter_for([searched("sleep divorce"), answered()])
        turn = adapter.answer("prompt")
        assert [call.query for call in turn.calls] == ["sleep divorce"]
        assert turn.searched
        # One request only: the scripted second response was never reached.
        assert len(adapter._client.messages.requests) == 1  # type: ignore[attr-defined]

    def test_a_malformed_call_is_recorded_not_raised(self) -> None:
        adapter = adapter_for(
            [Response("tool_use", [Block(type="tool_use", id="t", name="search", input={})])]
        )
        turn = adapter.answer("prompt")
        assert turn.calls[0].schema_error is not None

    def test_a_wrong_tool_is_recorded(self) -> None:
        turn = adapter_for([searched(name="calculator")]).answer("prompt")
        assert turn.calls[0].name == "calculator"

    def test_sampling_is_omitted_for_models_that_reject_it(self) -> None:
        """Opus 5 and Sonnet 5 return 400 when temperature is sent."""
        adapter = adapter_for([answered()], model_id="claude-opus-5")
        adapter.answer("prompt")
        assert "temperature" not in adapter._client.messages.requests[0]  # type: ignore[attr-defined]

    def test_sampling_is_sent_for_models_that_accept_it(self) -> None:
        adapter = adapter_for([answered()], model_id="claude-haiku-4-5")
        adapter.answer("prompt")
        assert "temperature" in adapter._client.messages.requests[0]  # type: ignore[attr-defined]

    def test_the_search_tool_is_not_strict(self) -> None:
        """Strict mode would make malformed calls impossible to observe."""
        adapter = adapter_for([answered()])
        adapter.answer("prompt")
        tool = adapter._client.messages.requests[0]["tools"][0]  # type: ignore[attr-defined]
        assert "strict" not in tool


class TestRunTasks:
    def test_writes_each_attempt_as_it_lands(self, tmp_path: Path) -> None:
        out = tmp_path / "attempts.jsonl"
        adapter = adapter_for([answered(), answered(), answered()])
        run_tasks([task("a"), task("b"), task("c")], "claude-opus-5", adapter, out_path=out)
        assert completed_task_ids(out) == {"a", "b", "c"}

    def test_a_ctrl_c_keeps_what_it_paid_for(self, tmp_path: Path) -> None:
        """Provider errors are recorded, but a real interrupt still stops the run
        — and everything already written survives it."""
        out = tmp_path / "attempts.jsonl"

        class Interrupted(FakeMessages):
            def create(self, **request: Any) -> Response:
                if len(self.requests) >= 1:
                    raise KeyboardInterrupt
                return super().create(**request)

        adapter = adapter_for([])
        adapter._client = Block(messages=Interrupted([answered()]))  # type: ignore[attr-defined]

        with pytest.raises(KeyboardInterrupt):
            run_tasks(
                [task("a"), task("b")], "claude-opus-5", adapter, out_path=out, concurrency=1
            )
        assert completed_task_ids(out) == {"a"}

    def test_a_provider_error_is_recorded_rather_than_raised(self, tmp_path: Path) -> None:
        out = tmp_path / "attempts.jsonl"

        class Broken(FakeMessages):
            def create(self, **request: Any) -> Response:
                raise ConnectionError("the provider went away")

        adapter = adapter_for([])
        adapter._client = Block(messages=Broken([]))  # type: ignore[attr-defined]

        attempts = run_tasks([task("a")], "m", adapter, out_path=out, concurrency=1)
        assert attempts[0].failed
        # Recorded, but not "done": a rerun must retry it.
        assert completed_task_ids(out) == set()

    def test_completed_ids_is_empty_when_nothing_has_run(self, tmp_path: Path) -> None:
        assert completed_task_ids(tmp_path / "absent.jsonl") == set()


class TestConcurrency:
    def test_every_item_is_recorded(self, tmp_path: Path) -> None:
        out = tmp_path / "attempts.jsonl"
        adapter = adapter_for([answered() for _ in range(20)])
        tasks = [task(f"t{i}") for i in range(20)]
        run_tasks(tasks, "claude-opus-5", adapter, out_path=out, concurrency=4)
        assert completed_task_ids(out) == {t.id for t in tasks}

    def test_serial_mode_still_works(self, tmp_path: Path) -> None:
        out = tmp_path / "attempts.jsonl"
        adapter = adapter_for([answered(), answered()])
        run_tasks([task("a"), task("b")], "claude-opus-5", adapter, out_path=out, concurrency=1)
        assert completed_task_ids(out) == {"a", "b"}

    def test_one_failure_does_not_lose_the_rest(self, tmp_path: Path) -> None:
        """A provider hiccup 300 items in should not throw away the run."""
        out = tmp_path / "attempts.jsonl"

        class SometimesBroken(FakeMessages):
            def create(self, **request: Any) -> Response:
                prompt = request["messages"][0]["content"]
                if "boom" in prompt:
                    raise ConnectionError("the provider went away")
                return Response("end_turn", [Block(type="text", text="fine")])

        adapter = adapter_for([])
        adapter._client = Block(messages=SometimesBroken([]))  # type: ignore[attr-defined]

        good = task("good")
        bad = ToolUseTask(
            id="bad",
            bucket=Bucket.MEMORY,
            prompt="boom",
            gold_answer=["x"],
            source="test",
            subcategory="test",
        )
        attempts = run_tasks([good, bad], "m", adapter, out_path=out, concurrency=2)
        by_id = {a.task_id: a for a in attempts}
        assert by_id["good"].answer == "fine"
        assert by_id["bad"].failed
        assert "ConnectionError" in by_id["bad"].error
        # The good one is done; the failure is left for a rerun to retry.
        assert completed_task_ids(out) == {"good"}


class TestProviderErrorExplanation:
    """Some provider errors are not ours to fix, and should say so."""

    def test_the_vllm_tool_choice_error_is_explained(self) -> None:
        from llmsearchbench.harness.openai_compat import ChatCompletionsAdapter

        raw = (
            '{"error":{"message":"tool choice requires '
            '--enable-auto-tool-choice and --tool-call-parser to be set"}}'
        )
        explained = ChatCompletionsAdapter.explain(raw)
        assert "cannot run until the provider sets those flags" in explained
        assert "Nothing to fix on this side" in explained

    def test_an_unrecognised_error_is_passed_through_unchanged(self) -> None:
        from llmsearchbench.harness.openai_compat import ChatCompletionsAdapter

        assert ChatCompletionsAdapter.explain("rate limited") == "rate limited"


class TestPromptedProtocol:
    """A provider with tool calling disabled can still be measured, with a
    caveat attached to every number it produces."""

    def _adapter(self) -> object:
        """A catalogued model, switched to the prompted protocol.

        Built here rather than named: the protocol is a property of a
        provider's server settings, and a provider that fixes its flags should
        not break this test.
        """
        from llmsearchbench.harness.openai_compat import OpenRouterAdapter
        from llmsearchbench.providers import get_model
        from llmsearchbench.types.enums import ToolProtocol

        adapter = OpenRouterAdapter.__new__(OpenRouterAdapter)
        adapter._spec = get_model("qwen/qwen3-8b").model_copy(  # type: ignore[attr-defined]
            update={"tool_protocol": ToolProtocol.PROMPTED}
        )
        adapter._effort = "high"  # type: ignore[attr-defined]
        adapter._api_key = "test"  # type: ignore[attr-defined]
        return adapter

    def test_the_payload_carries_no_tools(self) -> None:
        """`tools` is exactly what such a server rejects."""
        payload = self._adapter()._payload("who?", 0.0)  # type: ignore[attr-defined]
        assert "tools" not in payload
        assert "tool_choice" not in payload

    def test_the_tool_is_described_in_the_prompt_instead(self) -> None:
        payload = self._adapter()._payload("who?", 0.0)  # type: ignore[attr-defined]
        content = payload["messages"][0]["content"]
        assert "SEARCH:" in content
        assert content.endswith("who?")

    def test_a_native_model_is_unaffected(self) -> None:
        from llmsearchbench.harness.openai_compat import OpenRouterAdapter
        from llmsearchbench.providers import get_model

        adapter = OpenRouterAdapter.__new__(OpenRouterAdapter)
        adapter._spec = get_model("qwen/qwen3-8b")  # type: ignore[attr-defined]
        adapter._api_key = "test"  # type: ignore[attr-defined]
        payload = adapter._payload("who?", 0.0)
        assert payload["tools"]
        assert payload["messages"][0]["content"] == "who?"


class TestParsePromptedCall:
    def test_a_plain_call(self) -> None:
        from llmsearchbench.harness.openai_compat import parse_prompted_call

        call = parse_prompted_call("SEARCH: population of Doha 2026")
        assert call is not None
        assert call.arguments == {"query": "population of Doha 2026"}
        assert call.schema_error is None

    def test_markdown_around_the_keyword_is_not_a_malformed_call(self) -> None:
        from llmsearchbench.harness.openai_compat import parse_prompted_call

        call = parse_prompted_call("**SEARCH:** who won in 2026")
        assert call is not None and call.arguments == {"query": "who won in 2026"}

    def test_an_empty_query_is_recorded_as_malformed(self) -> None:
        from llmsearchbench.harness.openai_compat import parse_prompted_call

        call = parse_prompted_call("SEARCH:")
        assert call is not None and call.schema_error is not None

    def test_an_answer_is_not_a_call(self) -> None:
        from llmsearchbench.harness.openai_compat import parse_prompted_call

        assert parse_prompted_call("The capital of France is Paris.") is None

    def test_a_call_after_some_preamble_still_counts(self) -> None:
        """The decision is what is measured, not obedience about line count."""
        from llmsearchbench.harness.openai_compat import parse_prompted_call

        call = parse_prompted_call("I do not know this offhand.\nSEARCH: Avey Olive model")
        assert call is not None and call.arguments == {"query": "Avey Olive model"}


class TestTextEmittedCalls:
    """Some models write the call into the reply instead of the tool field.

    Their provider serves them without a matching tool-call parser, so the
    text arrives verbatim. The decision to search was still made.
    """

    def test_a_qwen_style_call_is_read(self) -> None:
        from llmsearchbench.harness.openai_compat import parse_text_calls

        text = (
            "I will look this up.\n<function=search>\n"
            "<parameter=query>\nstreams parallelize\n</parameter>\n</function>"
        )
        calls = parse_text_calls(text)
        assert len(calls) == 1
        assert calls[0].name == "search"
        assert calls[0].query == "streams parallelize"
        assert calls[0].emitted_as_text

    def test_a_chatml_style_call_is_read(self) -> None:
        from llmsearchbench.harness.openai_compat import parse_text_calls

        calls = parse_text_calls(
            '<tool_call>{"name": "search", "arguments": {"query": "who won"}}</tool_call>'
        )
        assert len(calls) == 1 and calls[0].query == "who won"
        assert calls[0].emitted_as_text

    def test_ordinary_prose_is_not_a_call(self) -> None:
        from llmsearchbench.harness.openai_compat import parse_text_calls

        assert parse_text_calls("The function search() is not being called here.") == []

    def test_scoring_reports_it_as_a_call_problem(self) -> None:
        from llmsearchbench.scoring.tooluse import CallProblem, inspect_calls
        from llmsearchbench.types.tooluse import ToolCall, ToolUseAttempt

        attempt = ToolUseAttempt(
            task_id="t",
            model="m",
            answer="text",
            calls=[ToolCall(name="search", arguments={"query": "x"}, emitted_as_text=True)],
        )
        assert inspect_calls(attempt) == [CallProblem.TEXT_CALL]
        # Still a search: the model decided to look it up.
        assert attempt.searched


class TestEmptyReplies:
    """A reply with no text and no call is not a decision."""

    def test_an_empty_reply_is_recorded_as_a_failure(self, tmp_path: Path) -> None:
        out = tmp_path / "attempts.jsonl"
        adapter = adapter_for([Response("end_turn", [Block(type="text", text="   ")])])
        attempts = run_tasks([task("a")], "m", adapter, out_path=out, concurrency=1)
        assert attempts[0].failed
        assert "no answer and no tool call" in attempts[0].error
        # Not done, so a rerun retries it rather than scoring the silence.
        assert completed_task_ids(out) == set()

    def test_a_truncated_reply_keeps_its_stop_reason(self, tmp_path: Path) -> None:
        """A model that spent the whole budget thinking never decided."""
        adapter = adapter_for([Response("max_tokens", [])])
        attempts = run_tasks(
            [task("a")], "m", adapter, out_path=tmp_path / "a.jsonl", concurrency=1
        )
        assert attempts[0].failed and "max_tokens" in attempts[0].error

    def test_an_answer_is_still_a_decision(self, tmp_path: Path) -> None:
        adapter = adapter_for([answered("Paris.")])
        attempts = run_tasks(
            [task("a")], "m", adapter, out_path=tmp_path / "a.jsonl", concurrency=1
        )
        assert not attempts[0].failed
