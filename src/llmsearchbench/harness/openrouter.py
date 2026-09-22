"""OpenRouter adapter.

OpenRouter fronts many providers behind one key and an OpenAI-shaped
chat-completions API. That makes it the cheapest way to get a second and third
model into the benchmark without a separate account each.

One caveat worth stating plainly: routing a model through OpenRouter is not
identical to calling its own API. Tool-call formatting, system-prompt handling,
and default sampling can all differ slightly from first-party. A run's manifest
records which route was used, and results from different routes are not
strictly comparable.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from llmsearchbench.harness.config import HarnessConfig
from llmsearchbench.harness.protocols import SearchBackend
from llmsearchbench.providers import ModelSpec
from llmsearchbench.types.tooluse import ToolCall

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT = 120.0

#: The same one tool, in the shape OpenRouter expects. Not marked strict, for
#: the same reason as the Anthropic definition: a malformed call has to stay
#: observable.
SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search",
        "description": (
            "Search the web for current or obscure information. "
            "Use it only when you do not already know the answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The search query."}},
            "required": ["query"],
        },
    },
}


class OpenRouterError(RuntimeError):
    """OpenRouter refused the request or could not be reached."""


def _post(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/younissk/LLMSearchBench",
            "X-Title": "LLMSearchBench",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
            body: dict[str, Any] = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise OpenRouterError(f"{error.code}: {error.read()[:300]!r}") from error
    except urllib.error.URLError as error:
        raise OpenRouterError(f"unreachable: {error.reason}") from error

    if "error" in body:
        raise OpenRouterError(str(body["error"]))
    return body


def parse_arguments(raw: str) -> tuple[dict[str, str], str | None]:
    """Parse a tool call's JSON arguments, reporting what was wrong.

    OpenRouter hands arguments back as a JSON *string*, so malformed JSON is a
    real failure mode here that the Anthropic path does not have.
    """
    try:
        parsed = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as error:
        return {}, f"arguments are not valid JSON: {error.msg}"

    if not isinstance(parsed, dict):
        return {}, f"arguments must be an object, got {type(parsed).__name__}"

    arguments = {str(key): str(value) for key, value in parsed.items()}
    unexpected = set(arguments) - {"query"}
    if "query" not in arguments:
        return arguments, "missing required argument 'query'"
    if unexpected:
        return arguments, f"unexpected argument(s): {', '.join(sorted(unexpected))}"
    return arguments, None


class OpenRouterAdapter:
    """Runs one prompt through OpenRouter, logging every tool call."""

    def __init__(self, spec: ModelSpec, *, effort: str = "high") -> None:
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Put it in .env or export it; see .env.example."
            )
        self._spec = spec
        self._effort = effort
        self._api_key = api_key

    def answer(
        self,
        prompt: str,
        backend: SearchBackend,
        config: HarnessConfig,
    ) -> tuple[str, list[ToolCall], int, int, float]:
        from llmsearchbench.harness.adapters import _render

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        calls: list[ToolCall] = []
        tokens_in = tokens_out = 0
        started = time.monotonic()

        for _ in range(config.max_calls + 2):
            payload: dict[str, Any] = {
                "model": self._spec.id,
                "messages": messages,
                "tools": [SEARCH_TOOL],
                "max_tokens": 4096,
            }
            if self._spec.supports_temperature:
                payload["temperature"] = config.temperature

            body = _post(payload, self._api_key)
            usage = body.get("usage") or {}
            tokens_in += int(usage.get("prompt_tokens", 0))
            tokens_out += int(usage.get("completion_tokens", 0))

            choices = body.get("choices") or []
            if not choices:
                raise OpenRouterError("response contained no choices")
            message = choices[0].get("message") or {}
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                text = str(message.get("content") or "")
                return text, calls, tokens_in, tokens_out, time.monotonic() - started

            messages.append(message)
            for call in tool_calls:
                function = call.get("function") or {}
                name = str(function.get("name", ""))
                arguments, schema_error = parse_arguments(str(function.get("arguments", "")))
                calls.append(
                    ToolCall(name=name, arguments=arguments, schema_error=schema_error)
                )

                if name != "search":
                    content = f"No tool named {name!r} is available."
                elif schema_error is not None:
                    content = f"Invalid arguments: {schema_error}"
                elif not arguments.get("query", "").strip():
                    content = "The query was empty."
                else:
                    content = _render(backend.search(arguments["query"], config.top_k))

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": content or "No results.",
                    }
                )

        return "", calls, tokens_in, tokens_out, time.monotonic() - started
