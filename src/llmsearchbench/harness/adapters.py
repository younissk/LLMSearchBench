"""Talking to a model.

Only Anthropic is wired up. Adding a provider means writing one class with an
`answer` method and registering it below — the run loop and the scorer do not
change.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic import Field

from llmsearchbench.harness.config import HarnessConfig
from llmsearchbench.harness.protocols import Document, SearchBackend
from llmsearchbench.providers import ModelSpec, get_model, get_provider
from llmsearchbench.types import BenchModel
from llmsearchbench.types.tooluse import ToolCall

if TYPE_CHECKING:
    from llmsearchbench.harness.openrouter import OpenRouterAdapter

#: The one tool the model is offered. Deliberately *not* `strict`: strict mode
#: guarantees schema-valid arguments, which would make malformed calls
#: impossible to observe — and observing them is half the point of this task.
SEARCH_TOOL: dict[str, Any] = {
    "name": "search",
    "description": (
        "Search the web for current or obscure information. "
        "Use it only when you do not already know the answer."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            }
        },
        "required": ["query"],
    },
}


class NotConfiguredError(RuntimeError):
    """The model has no adapter, or its credential is missing."""


class Turn(BenchModel):
    """Everything one adapter observed while answering one prompt."""

    answer: str
    calls: list[ToolCall]
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    #: Included in `tokens_out` where the provider separates it out; 0 otherwise.
    reasoning_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    latency_s: float = Field(ge=0)
    turns: int = Field(ge=0)
    stop_reason: str = ""


def validate_search_arguments(raw: object) -> tuple[dict[str, str], str | None]:
    """Check tool arguments against the search tool's schema.

    Returns the normalised arguments and, when the call was malformed, the
    reason. Done here rather than by the API so a bad call is recorded as data
    instead of raising.
    """
    if not isinstance(raw, dict):
        return {}, f"arguments must be an object, got {type(raw).__name__}"

    arguments = {str(key): str(value) for key, value in raw.items()}
    unexpected = set(arguments) - {"query"}
    if "query" not in arguments:
        return arguments, "missing required argument 'query'"
    if unexpected:
        return arguments, f"unexpected argument(s): {', '.join(sorted(unexpected))}"
    return arguments, None


class AnthropicAdapter:
    """Runs one prompt through the Messages API, logging every tool call."""

    def __init__(self, spec: ModelSpec, *, effort: str = "high") -> None:
        import anthropic

        provider = get_provider(spec.provider)
        api_key = os.environ.get(provider.env_var, "").strip()
        if not api_key:
            raise NotConfiguredError(
                f"{provider.env_var} is not set. Put it in .env or export it; see .env.example."
            )
        self._spec = spec
        self._effort = effort
        self._client = anthropic.Anthropic(api_key=api_key)

    def answer(
        self,
        prompt: str,
        backend: SearchBackend,
        config: HarnessConfig,
    ) -> Turn:
        """Run one prompt to completion and report everything observed."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        calls: list[ToolCall] = []
        tokens_in = tokens_out = cached = 0
        turns = 0
        stop_reason = ""
        started = time.monotonic()

        # One extra turn past the budget, so a model that keeps calling is
        # recorded as over-budget rather than silently truncated.
        for _ in range(config.max_calls + 2):
            request: dict[str, Any] = {
                "model": self._spec.id,
                "max_tokens": 4096,
                "messages": messages,
                "tools": [SEARCH_TOOL],
                "output_config": {"effort": self._effort},
            }
            if self._spec.supports_temperature:
                request["temperature"] = config.temperature

            response = self._client.messages.create(**request)
            turns += 1
            tokens_in += response.usage.input_tokens
            tokens_out += response.usage.output_tokens
            cached += getattr(response.usage, "cache_read_input_tokens", 0) or 0
            stop_reason = str(response.stop_reason or "")

            if response.stop_reason != "tool_use":
                text = "".join(block.text for block in response.content if block.type == "text")
                return Turn(
                    answer=text,
                    calls=calls,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    # Anthropic bills thinking inside output tokens and does not
                    # break it out, so this stays zero on this route.
                    reasoning_tokens=0,
                    cached_tokens=cached,
                    latency_s=time.monotonic() - started,
                    turns=turns,
                    stop_reason=stop_reason,
                )

            messages.append({"role": "assistant", "content": response.content})
            results: list[dict[str, Any]] = []

            for block in response.content:
                if block.type != "tool_use":
                    continue
                arguments, schema_error = validate_search_arguments(block.input)
                calls.append(
                    ToolCall(
                        name=block.name,
                        arguments=arguments,
                        schema_error=schema_error,
                    )
                )
                body = _tool_result_body(block.name, arguments, schema_error, backend, config)
                results.append({"type": "tool_result", "tool_use_id": block.id, **body})

            messages.append({"role": "user", "content": results})

        return Turn(
            answer="",
            calls=calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            reasoning_tokens=0,
            cached_tokens=cached,
            latency_s=time.monotonic() - started,
            turns=turns,
            stop_reason=stop_reason,
        )


def _tool_result_body(
    name: str,
    arguments: dict[str, str],
    schema_error: str | None,
    backend: SearchBackend,
    config: HarnessConfig,
) -> dict[str, Any]:
    """The result handed back for one call, including for a bad call.

    A malformed call still gets an error result rather than an exception: the
    model should be given the chance to recover, and the mistake is already
    recorded.
    """
    if name != "search":
        return {"content": f"No tool named {name!r} is available.", "is_error": True}
    if schema_error is not None:
        return {"content": f"Invalid arguments: {schema_error}", "is_error": True}

    query = arguments.get("query", "").strip()
    if not query:
        return {"content": "The query was empty.", "is_error": True}

    documents = backend.search(query, config.top_k)
    return {"content": _render(documents) or "No results."}


def _render(documents: Sequence[Document]) -> str:
    return "\n\n".join(
        f"[{index}] {doc.title}\n{doc.url}\n{doc.text}"
        for index, doc in enumerate(documents, start=1)
    )


def build_adapter(
    model_id: str, *, effort: str = "high"
) -> AnthropicAdapter | OpenRouterAdapter:
    """Return the adapter for a model id.

    Fails loudly for an unknown id or a missing key: a benchmark that quietly
    substitutes a different model produces numbers nobody can place.
    """
    from llmsearchbench.harness.openrouter import OpenRouterAdapter

    spec = get_model(model_id)
    provider = get_provider(spec.provider)
    if provider.key == "anthropic":
        return AnthropicAdapter(spec, effort=effort)
    if provider.key == "openrouter":
        try:
            return OpenRouterAdapter(spec, effort=effort)
        except RuntimeError as error:
            raise NotConfiguredError(str(error)) from None
    raise NotConfiguredError(
        f"no adapter is wired up for provider {provider.key!r}. "
        "Add one in src/llmsearchbench/harness/adapters.py."
    )
