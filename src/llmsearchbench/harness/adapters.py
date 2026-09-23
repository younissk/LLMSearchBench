"""Talking to a model.

The model is offered one tool and never gets to use it: the moment it reaches
for `search`, the episode ends and the call is recorded. This task asks whether
a model knows *when* to search, and that decision is made before any result
comes back — so no search is ever executed, and no search API is involved.
"""

from __future__ import annotations

import os
import time
from typing import Any

from pydantic import Field

from llmsearchbench.providers import ModelSpec, get_model, get_provider
from llmsearchbench.types import BenchModel
from llmsearchbench.types.tooluse import ToolCall

#: The one tool the model is offered. Deliberately *not* `strict`: strict mode
#: guarantees schema-valid arguments, which would make a malformed call
#: impossible to observe — and observing them is part of what this measures.
SEARCH_TOOL: dict[str, Any] = {
    "name": "search",
    "description": (
        "Search the web for current or obscure information. "
        "Use it only when you do not already know the answer."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The search query."}},
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
    stop_reason: str = ""

    @property
    def searched(self) -> bool:
        return bool(self.calls)


def validate_search_arguments(raw: object) -> tuple[dict[str, str], str | None]:
    """Check tool arguments against the search tool's schema.

    Returns the normalised arguments and, when the call was malformed, the
    reason. Checked here rather than by the API so a bad call is recorded as
    data instead of raising.
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


def as_call(name: str, raw: object) -> ToolCall:
    """Record one tool call, validated but never executed."""
    arguments, schema_error = validate_search_arguments(raw)
    return ToolCall(name=name, arguments=arguments, schema_error=schema_error)


class AnthropicAdapter:
    """One prompt, one response, and whether it reached for the tool."""

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

    def answer(self, prompt: str, temperature: float = 0.0) -> Turn:
        started = time.monotonic()
        request: dict[str, Any] = {
            "model": self._spec.id,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [SEARCH_TOOL],
            "output_config": {"effort": self._effort},
        }
        if self._spec.supports_temperature:
            request["temperature"] = temperature

        response = self._client.messages.create(**request)
        calls = [
            as_call(block.name, block.input)
            for block in response.content
            if block.type == "tool_use"
        ]
        text = "".join(block.text for block in response.content if block.type == "text")

        return Turn(
            answer=text,
            calls=calls,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            # Anthropic bills thinking inside output tokens and does not break
            # it out, so this stays zero on this route.
            reasoning_tokens=0,
            cached_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            latency_s=time.monotonic() - started,
            stop_reason=str(response.stop_reason or ""),
        )


def build_adapter(model_id: str, *, effort: str = "high") -> Any:
    """Return the adapter for a model id.

    Fails loudly for an unknown id or a missing key: a benchmark that quietly
    substitutes a different model produces numbers nobody can place.
    """
    from llmsearchbench.harness.openai_compat import MoonshotAdapter, OpenRouterAdapter

    spec = get_model(model_id)
    provider = get_provider(spec.provider)
    if provider.key == "anthropic":
        return AnthropicAdapter(spec, effort=effort)

    compatible = {"openrouter": OpenRouterAdapter, "moonshot": MoonshotAdapter}
    if provider.key in compatible:
        try:
            return compatible[provider.key](spec, effort=effort)
        except RuntimeError as error:
            raise NotConfiguredError(str(error)) from None

    raise NotConfiguredError(
        f"no adapter is wired up for provider {provider.key!r}. "
        "Add one in src/llmsearchbench/harness/openai_compat.py."
    )
