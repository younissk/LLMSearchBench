"""Record which models can be asked for a schema-constrained answer.

    uv run python scripts/model_capabilities.py

The search-result-discrimination task wants three things back — a ranking, the
candidates the model would cite, and an answer — and a reply the harness cannot
parse is not a wrong answer, it is no answer. Where a provider supports
`response_format: json_schema`, the shape can be enforced; where it does not,
the harness has to ask in the prompt and parse leniently.

Which is which is a provider fact that moves, so it is fetched and recorded
with a date rather than assumed, exactly like prices. Written to
`data/model_capabilities.json`, which is committed; the site build never calls
OpenRouter.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from typing import Any

from llmsearchbench.paths import MODEL_CAPABILITIES
from llmsearchbench.providers import MODELS

OPENROUTER = "https://openrouter.ai/api/v1/models"

#: Parameters worth recording. `structured_outputs` is the strict one — a JSON
#: Schema the provider enforces; `response_format` alone only promises JSON.
PARAMETERS = ("structured_outputs", "response_format", "tools", "reasoning")


def wire_ids(model_id: str) -> tuple[str, ...]:
    """Ids this model might appear under in OpenRouter's catalogue."""
    if model_id.startswith("moonshot/"):
        return (model_id, "moonshotai/" + model_id.split("/", 1)[1])
    return (model_id,)


def main() -> None:
    with urllib.request.urlopen(OPENROUTER, timeout=40) as response:
        catalogue: dict[str, Any] = {
            entry["id"]: entry for entry in json.load(response)["data"]
        }

    today = date.today().isoformat()
    records: dict[str, dict[str, object]] = {}
    unlisted: list[str] = []

    for model_id in sorted(MODELS):
        entry = next(
            (catalogue[wire] for wire in wire_ids(model_id) if wire in catalogue), None
        )
        if entry is None:
            unlisted.append(model_id)
            continue
        supported = set(entry.get("supported_parameters") or [])
        records[model_id] = {parameter: parameter in supported for parameter in PARAMETERS} | {
            "checked": today
        }

    MODEL_CAPABILITIES.write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    strict = sum(1 for record in records.values() if record["structured_outputs"])
    print(f"wrote {MODEL_CAPABILITIES} ({len(records)} model(s))")
    print(f"  {strict} enforce a JSON schema; {len(records) - strict} do not")
    for model_id, record in sorted(records.items()):
        if not record["structured_outputs"]:
            shape = "json only" if record["response_format"] else "no shape at all"
            print(f"    prompted JSON needed: {model_id}  ({shape})")
    for model_id in unlisted:
        print(f"  not in the OpenRouter catalogue, so not recorded: {model_id}")


if __name__ == "__main__":
    main()
