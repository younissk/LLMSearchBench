"""Adapters for providers that speak the OpenAI chat-completions shape.

OpenRouter and Moonshot both do, so the request/response handling lives here
once and each provider supplies only its endpoint, credential, and headers.

As on the Anthropic route, the tool is offered and never executed: the call is
recorded and the episode ends.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, ClassVar

from llmsearchbench.harness.adapters import Turn
from llmsearchbench.providers import ModelSpec
from llmsearchbench.types.tooluse import ToolCall

#: Socket timeout. urllib applies this per operation, not to the whole
#: request — a server that trickles bytes resets it indefinitely.
SOCKET_TIMEOUT = 60.0

#: Hard ceiling on one request, enforced while reading the body. Without it a
#: single item can hang a run forever.
DEADLINE = 180.0

#: How much body to read per chunk while checking the deadline.
CHUNK = 1 << 16

#: The one tool, in the shape these APIs expect. Deliberately not `strict`:
#: strict mode would make a malformed call impossible to observe.
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


class ChatCompletionsError(RuntimeError):
    """The provider refused the request or could not be reached."""


class RequestTimeoutError(RuntimeError):
    """One request went past its deadline and was abandoned."""


def read_with_deadline(response: Any, deadline: float) -> bytes:
    """Read a response body, giving up if it takes too long overall.

    Uses `read1`, which returns as soon as *any* data is available. Plain
    `read(n)` blocks until it has all n bytes, so a server that trickles keeps
    the call inside one `read` forever and the deadline below is never reached.
    """
    read = getattr(response, "read1", None) or response.read
    chunks: list[bytes] = []
    while True:
        if time.monotonic() > deadline:
            raise RequestTimeoutError(f"no complete response within {DEADLINE:.0f}s")
        chunk = read(CHUNK)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def parse_arguments(raw: str) -> tuple[dict[str, str], str | None]:
    """Parse a tool call's JSON arguments, reporting what was wrong.

    These APIs hand arguments back as a JSON *string*, so malformed JSON is a
    failure mode the Anthropic route does not have.
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


def reasoning_tokens(usage: dict[str, Any]) -> int:
    """Thinking tokens, where the provider reports them.

    Billed as output, so they are already inside `completion_tokens`.
    """
    details = usage.get("completion_tokens_details")
    return int(details.get("reasoning_tokens", 0) or 0) if isinstance(details, dict) else 0


def cached_tokens(usage: dict[str, Any]) -> int:
    details = usage.get("prompt_tokens_details")
    return int(details.get("cached_tokens", 0) or 0) if isinstance(details, dict) else 0


class ChatCompletionsAdapter:
    """One prompt, one response, and whether it reached for the tool."""

    #: Chat-completions endpoint.
    endpoint: str = ""
    #: Environment variable holding the credential.
    key_env: str = ""
    #: Anything else the provider wants on every request.
    extra_headers: ClassVar[dict[str, str]] = {}

    def __init__(self, spec: ModelSpec, *, effort: str = "high") -> None:
        api_key = os.environ.get(self.key_env, "").strip()
        if not api_key:
            raise RuntimeError(
                f"{self.key_env} is not set. Put it in .env or export it; see .env.example."
            )
        self._spec = spec
        self._effort = effort
        self._api_key = api_key

    def _payload(self, prompt: str, temperature: float) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.wire_name(self._spec.id),
            "messages": [{"role": "user", "content": prompt}],
            "tools": [SEARCH_TOOL],
            "max_tokens": 4096,
        }
        if self._spec.supports_temperature:
            payload["temperature"] = temperature
        return payload

    def wire_name(self, model_id: str) -> str:
        """The id this provider expects. Overridden where ours is prefixed."""
        return model_id

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                **self.extra_headers,
            },
            method="POST",
        )
        deadline = time.monotonic() + DEADLINE
        try:
            with urllib.request.urlopen(request, timeout=SOCKET_TIMEOUT) as response:
                body: dict[str, Any] = json.loads(read_with_deadline(response, deadline))
        except urllib.error.HTTPError as error:
            raise ChatCompletionsError(f"{error.code}: {error.read()[:300]!r}") from error
        except urllib.error.URLError as error:
            raise ChatCompletionsError(f"unreachable: {error.reason}") from error
        except RequestTimeoutError as error:
            raise ChatCompletionsError(str(error)) from error
        except TimeoutError as error:
            raise ChatCompletionsError(
                f"socket timed out after {SOCKET_TIMEOUT:.0f}s"
            ) from error

        if "error" in body:
            raise ChatCompletionsError(str(body["error"]))
        return body

    def answer(self, prompt: str, temperature: float = 0.0) -> Turn:
        started = time.monotonic()
        body = self._post(self._payload(prompt, temperature))

        usage = body.get("usage") or {}
        choices = body.get("choices") or []
        if not choices:
            raise ChatCompletionsError("response contained no choices")

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
            reasoning_tokens=reasoning_tokens(usage),
            cached_tokens=cached_tokens(usage),
            latency_s=time.monotonic() - started,
            stop_reason=str(choices[0].get("finish_reason") or ""),
        )


class OpenRouterAdapter(ChatCompletionsAdapter):
    """OpenRouter: one key, many providers.

    Routing a model through OpenRouter is not identical to calling its own API —
    tool-call formatting and default sampling can differ. The route is recorded
    with each run, and results from different routes are not strictly comparable.
    """

    endpoint = "https://openrouter.ai/api/v1/chat/completions"
    key_env = "OPENROUTER_API_KEY"
    extra_headers: ClassVar[dict[str, str]] = {
        "HTTP-Referer": "https://github.com/younissk/LLMSearchBench",
        "X-Title": "LLMSearchBench",
    }


class MoonshotAdapter(ChatCompletionsAdapter):
    """Moonshot's own API, for the Kimi models."""

    endpoint = "https://api.moonshot.ai/v1/chat/completions"
    key_env = "KIMI_API_KEY"

    def wire_name(self, model_id: str) -> str:
        # Catalogued as `moonshot/kimi-k3`; Moonshot wants the bare name.
        return model_id.split("/", 1)[-1]
