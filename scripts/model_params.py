"""Record how large each catalogued model actually is.

    uv run python scripts/model_params.py

Parameter counts come from the weights themselves: Hugging Face reports the
exact tensor total for a repo, so nothing here is read off a marketing page or
inferred from a name. A model whose repo is unknown, gated, or missing the
figure is left out rather than estimated — the point of the size chart is to
inform a fine-tuning decision, and a made-up number is worse than a gap.

Needs the network. Run it by hand when the catalogue changes; the result is
committed, so the site build never touches Hugging Face.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date
from typing import Any

from llmsearchbench.paths import MODEL_PARAMS
from llmsearchbench.providers import MODELS
from llmsearchbench.providers.weights import WEIGHTS

HUGGINGFACE = "https://huggingface.co/api/models/"
OUT = MODEL_PARAMS


def repo_for(model_id: str) -> str | None:
    """The weights repo for a catalogued id.

    Kimi is catalogued against Moonshot's own API under `moonshot/`, while the
    weights map uses the Hugging Face org name, so that one id is rewritten.
    """
    if model_id in WEIGHTS:
        return WEIGHTS[model_id]
    if model_id.startswith("moonshot/"):
        return WEIGHTS.get("moonshotai/" + model_id.split("/", 1)[1])
    return None


def parameters(repo: str) -> int | None:
    """Total tensor parameters, or None when the repo does not say."""
    try:
        with urllib.request.urlopen(HUGGINGFACE + repo, timeout=25) as response:
            model: dict[str, Any] = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    total = (model.get("safetensors") or {}).get("total")
    return int(total) if total else None


def main() -> None:
    today = date.today().isoformat()
    records: dict[str, dict[str, object]] = {}
    missing: list[str] = []

    for model_id in sorted(MODELS):
        repo = repo_for(model_id)
        if repo is None:
            missing.append(f"{model_id}: no weights repo recorded")
            continue
        total = parameters(repo)
        if total is None:
            missing.append(f"{model_id}: {repo} reports no tensor total")
            continue
        records[model_id] = {
            "repo": repo,
            "parameters": total,
            "source": f"https://huggingface.co/api/models/{repo}",
            "fetched": today,
        }
        print(f"{model_id:45} {total / 1e9:8.1f}B  {repo}")
        time.sleep(0.05)

    OUT.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT} ({len(records)} model(s))")
    for line in missing:
        print(f"  no size: {line}")


if __name__ == "__main__":
    main()
