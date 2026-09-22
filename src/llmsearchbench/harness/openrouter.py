"""OpenRouter adapter.

One key reaches many providers. As with the Anthropic route, the tool is
offered and never executed — the call is recorded and the episode ends.

One caveat worth stating: routing a model through OpenRouter is not identical
to calling its own API. Tool-call formatting and default sampling can differ.
Results from different routes are not strictly comparable.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from llmsearchbench.harness.adapters import Turn
from llmsearchbench.providers import ModelSpec
from llmsearchbench.types.tooluse import ToolCall

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT = 120.0

#: The same tool, in the shape OpenRouter expects.
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
    failure mode here that the Anthropic route does not have.
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


def _reasoning_tokens(usage: dict[str, Any]) -> int:
    """Thinking tokens, where the routed provider reports them.

    Billed as output, so they are already inside `completion_tokens`. Recording
    them separately is what shows a model spending 3,000 tokens deciding
    whether to search for a haiku.
    """
    details = usage.get("completion_tokens_details")
    return int(details.get("reasoning_tokens", 0) or 0) if isinstance(details, dict) else 0


def _cached_tokens(usage: dict[str, Any]) -> int:
    details = usage.get("prompt_tokens_details")
    return int(details.get("cached_tokens", 0) or 0) if isinstance(details, dict) else 0


class OpenRouterAdapter:
    """One prompt, one response, and whether it reached for the tool."""

    def __init__(self, spec: ModelSpec, *, effort: str = "high") -> None:
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Put it in .env or export it; see .env.example."
            )
        self._spec = spec
        self._effort = effort
        self._api_key = api_key

    def answer(self, prompt: str, temperature: float = 0.0) -> Turn:
        started = time.monotonic()
        payload: dict[str, Any] = {
            "model": self._spec.id,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [SEARCH_TOOL],
            "max_tokens": 4096,
        }
        if self._spec.supports_temperature:
            payload["temperature"] = temperature

        body = _post(payload, self._api_key)
        usage = body.get("usage") or {}
        choices = body.get("choices") or []
        if not choices:
            raise OpenRouterError("response contained no choices")

        message = choices[0].get("message") or {}
        calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            arguments, schema_error = parse_arguments(str(function.get("arguments", "")))
            calls.append(
                ToolCall(
                    name=str(function.get("name", "")),
                    arguments=arguments,
                    schema_error=schema_error,
                )
            )

        return Turn(
            answer=str(message.get("content") or ""),
            calls=calls,
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            reasoning_tokens=_reasoning_tokens(usage),
            cached_tokens=_cached_tokens(usage),
            latency_s=time.monotonic() - started,
            stop_reason=str(choices[0].get("finish_reason") or ""),
        )
