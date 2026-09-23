"""Adapters for providers that speak the OpenAI chat-completions shape.

OpenRouter and Moonshot both do, so the request/response handling lives here
once and each provider supplies only its endpoint, credential, and headers.

As on the Anthropic route, the tool is offered and never executed: the call is
recorded and the episode ends.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, ClassVar

from llmsearchbench.harness.adapters import Turn
from llmsearchbench.providers import ModelSpec
from llmsearchbench.types.enums import ToolProtocol
from llmsearchbench.types.tooluse import ToolCall

#: Socket timeout. urllib applies this per operation, not to the whole
#: request — a server that trickles bytes resets it indefinitely.
SOCKET_TIMEOUT = 60.0

#: Hard ceiling on one request, enforced while reading the body. Without it a
#: single item can hang a run forever.
DEADLINE = 180.0

#: How much body to read per chunk while checking the deadline.
CHUNK = 1 << 16

#: Waits between retries of a rate-limited request, in seconds. A 429 is the
#: provider asking for a slower pace, not a broken item, so retrying beats
#: recording 335 failures — which is what one run against a staging endpoint
#: did before this existed.
BACKOFF = (2.0, 8.0, 20.0)

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


#: Offered in the prompt instead of the `tools` field, for a provider whose
#: server has tool calling switched off. The wording tracks `SEARCH_TOOL` above
#: so the two protocols describe the same tool, and asks for one line so the
#: reply is parseable without guessing.
PROMPTED_PREAMBLE = """You have one tool available:

search(query: string) — Search the web for current or obscure information. \
Use it only when you do not already know the answer.

This connection cannot carry a real tool call, so to use the tool, reply with \
exactly one line and nothing else:

SEARCH: <the query>

If you do not need the tool, answer directly and do not write that line.

"""

#: A prompted call. Tolerant about markdown around the keyword — a model that
#: writes `**SEARCH:** paris population` has made the decision this task
#: measures, and punishing the asterisks would measure formatting instead.
PROMPTED_CALL = re.compile(
    r"^[\s>*`_\-]*search\s*:\s*(?P<query>.*)$", re.IGNORECASE | re.MULTILINE
)


def parse_prompted_call(text: str) -> ToolCall | None:
    """Read a prompted tool call out of reply text, if there is one.

    Returns `None` when the model answered instead — which is the same signal
    as an empty `tool_calls` list on the native route.
    """
    match = PROMPTED_CALL.search(text)
    if match is None:
        return None

    query = match.group("query").strip().strip('`"*_').strip()
    if not query:
        return ToolCall(
            name="search", arguments={}, schema_error="missing required argument 'query'"
        )
    return ToolCall(name="search", arguments={"query": query}, schema_error=None)


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


def retry_after(error: urllib.error.HTTPError) -> float | None:
    """The provider's own pace, when it names one.

    Only the seconds form is honoured; the HTTP-date form is rare here and
    guessing at a date parse would be worse than the fixed backoff.
    """
    raw = error.headers.get("Retry-After") if error.headers else None
    try:
        return max(0.0, float(str(raw))) if raw else None
    except ValueError:
        return None


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

    @property
    def prompted(self) -> bool:
        return self._spec.tool_protocol is ToolProtocol.PROMPTED

    def _payload(self, prompt: str, temperature: float) -> dict[str, Any]:
        content = PROMPTED_PREAMBLE + prompt if self.prompted else prompt
        payload: dict[str, Any] = {
            "model": self.wire_name(self._spec.id),
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 4096,
        }
        # A server with tool calling disabled rejects the request outright when
        # `tools` is present, whatever `tool_choice` says.
        if not self.prompted:
            payload["tools"] = [SEARCH_TOOL]
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
        for wait in (*BACKOFF, None):
            deadline = time.monotonic() + DEADLINE
            try:
                with urllib.request.urlopen(request, timeout=SOCKET_TIMEOUT) as response:
                    body: dict[str, Any] = json.loads(read_with_deadline(response, deadline))
                break
            except urllib.error.HTTPError as error:
                detail = error.read()[:400].decode(errors="replace")
                if error.code == 429 and wait is not None:
                    time.sleep(retry_after(error) or wait)
                    continue
                raise ChatCompletionsError(f"{error.code}: {self.explain(detail)}") from error
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

    @staticmethod
    def explain(message: str) -> str:
        """Turn a provider error into something actionable where we can.

        The vLLM tool-choice error is worth catching by hand: it is a
        server-side launch flag, so no amount of retrying or rephrasing on our
        side will fix it, and the raw message does not say that.
        """
        if "enable-auto-tool-choice" in message:
            return (
                "the provider's vLLM server was started without tool calling "
                "enabled (--enable-auto-tool-choice and --tool-call-parser). "
                "This benchmark needs the model to choose freely whether to "
                "call the tool, so it cannot run until the provider sets those "
                "flags. Nothing to fix on this side."
            )
        return message

    def answer(self, prompt: str, temperature: float = 0.0) -> Turn:
        started = time.monotonic()
        body = self._post(self._payload(prompt, temperature))

        usage = body.get("usage") or {}
        choices = body.get("choices") or []
        if not choices:
            raise ChatCompletionsError("response contained no choices")

        message = choices[0].get("message") or {}
        text = str(message.get("content") or "")

        calls: list[ToolCall] = []
        if self.prompted:
            prompted_call = parse_prompted_call(text)
            if prompted_call is not None:
                calls.append(prompted_call)
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
            answer=text,
            calls=calls,
            tool_protocol=self._spec.tool_protocol,
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


class AveyAdapter(ChatCompletionsAdapter):
    """Avey's hosted endpoint.

    Avey also exposes an OpenAI *Responses*-shaped route at `/llm/responses`,
    but the chat-completions route is what this benchmark needs, because it is
    the one that carries `tools`.
    """

    endpoint = "https://staging1.api.avey.ai/llm/chat/completions"
    key_env = "AVEY_API_KEY"


class MoonshotAdapter(ChatCompletionsAdapter):
    """Moonshot's own API, for the Kimi models."""

    endpoint = "https://api.moonshot.ai/v1/chat/completions"
    key_env = "KIMI_API_KEY"

    def wire_name(self, model_id: str) -> str:
        # Catalogued as `moonshot/kimi-k3`; Moonshot wants the bare name.
        return model_id.split("/", 1)[-1]
