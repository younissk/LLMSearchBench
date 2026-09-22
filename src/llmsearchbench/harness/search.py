"""Search backends.

Every model in a release must hit the same backend, or the run is not
comparable — so which backend was used is recorded in the run manifest.

Requests go through `urllib` rather than a third-party HTTP client: the
payloads are small and this keeps the dependency list to the Anthropic SDK.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Sequence

from llmsearchbench.harness.protocols import Document

DEFAULT_TIMEOUT = 20.0


class SearchError(RuntimeError):
    """The backend could not be reached, or refused the request."""


class BackendNotConfiguredError(RuntimeError):
    """The chosen backend has no credential in the environment."""


def _post_json(
    url: str,
    payload: dict[str, object],
    headers: dict[str, str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body: dict[str, object] = json.loads(response.read())
            return body
    except urllib.error.HTTPError as error:
        raise SearchError(f"{url} returned {error.code}: {error.read()[:200]!r}") from error
    except urllib.error.URLError as error:
        raise SearchError(f"{url} unreachable: {error.reason}") from error


def _get_json(
    url: str, headers: dict[str, str], *, timeout: float = DEFAULT_TIMEOUT
) -> dict[str, object]:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body: dict[str, object] = json.loads(response.read())
            return body
    except urllib.error.HTTPError as error:
        raise SearchError(f"{url} returned {error.code}: {error.read()[:200]!r}") from error
    except urllib.error.URLError as error:
        raise SearchError(f"{url} unreachable: {error.reason}") from error


class TavilyBackend:
    """Tavily search. Key in `TAVILY_API_KEY`."""

    key_env = "TAVILY_API_KEY"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(self, query: str, top_k: int) -> Sequence[Document]:
        body = _post_json(
            "https://api.tavily.com/search",
            {
                "api_key": self._api_key,
                "query": query,
                "max_results": top_k,
                "search_depth": "basic",
            },
            {},
        )
        results = body.get("results") or []
        documents: list[Document] = []
        for item in results if isinstance(results, list) else []:
            if not isinstance(item, dict):
                continue
            documents.append(
                Document(
                    url=str(item.get("url", "")),
                    title=str(item.get("title", "")),
                    text=str(item.get("content", "")),
                )
            )
        return documents[:top_k]


class BraveBackend:
    """Brave Search. Key in `BRAVE_API_KEY`."""

    key_env = "BRAVE_API_KEY"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(self, query: str, top_k: int) -> Sequence[Document]:
        from urllib.parse import urlencode

        url = "https://api.search.brave.com/res/v1/web/search?" + urlencode(
            {"q": query, "count": top_k}
        )
        body = _get_json(
            url,
            {
                "Accept": "application/json",
                "X-Subscription-Token": self._api_key,
            },
        )
        web = body.get("web")
        results = web.get("results", []) if isinstance(web, dict) else []
        documents: list[Document] = []
        for item in results if isinstance(results, list) else []:
            if not isinstance(item, dict):
                continue
            documents.append(
                Document(
                    url=str(item.get("url", "")),
                    title=str(item.get("title", "")),
                    text=str(item.get("description", "")),
                )
            )
        return documents[:top_k]


class SerperBackend:
    """Serper (Google results). Key in `SERPER_API_KEY`."""

    key_env = "SERPER_API_KEY"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(self, query: str, top_k: int) -> Sequence[Document]:
        body = _post_json(
            "https://google.serper.dev/search",
            {"q": query, "num": top_k},
            {"X-API-KEY": self._api_key},
        )
        results = body.get("organic") or []
        documents: list[Document] = []
        for item in results if isinstance(results, list) else []:
            if not isinstance(item, dict):
                continue
            documents.append(
                Document(
                    url=str(item.get("link", "")),
                    title=str(item.get("title", "")),
                    text=str(item.get("snippet", "")),
                )
            )
        return documents[:top_k]


class NullBackend:
    """Answers every query with nothing. Needs no key and no network.

    For checking that a run works end to end before paying for a search
    subscription. The tool decision and the call quality are still measured
    truthfully — the model really did choose to search — but answers on the
    search bucket cannot be right, because nothing was ever retrieved. A run on
    this backend is not publishable, and `llmsearchbench run` says so.
    """

    key_env = ""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def search(self, query: str, top_k: int) -> Sequence[Document]:  # noqa: ARG002
        return []


#: Backends that return real results. `null` is deliberately excluded from
#: anything that treats a run as publishable.
LIVE_BACKENDS = ("tavily", "brave", "serper")

BACKENDS: dict[str, type[TavilyBackend | BraveBackend | SerperBackend | NullBackend]] = {
    "tavily": TavilyBackend,
    "brave": BraveBackend,
    "serper": SerperBackend,
    "null": NullBackend,
}


def build_backend(name: str) -> TavilyBackend | BraveBackend | SerperBackend | NullBackend:
    """Construct a backend by name, reading its key from the environment."""
    try:
        backend_class = BACKENDS[name]
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise BackendNotConfiguredError(
            f"unknown search backend {name!r}. Known: {known}."
        ) from None

    if backend_class is NullBackend:
        return NullBackend()

    api_key = os.environ.get(backend_class.key_env, "").strip()
    if not api_key:
        raise BackendNotConfiguredError(
            f"{backend_class.key_env} is not set. Put it in .env or export it; "
            f"see .env.example."
        )
    return backend_class(api_key)
