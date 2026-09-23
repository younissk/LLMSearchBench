"""Regenerate the open-weight coverage table in the documentation.

    uv run python scripts/open_weight_coverage.py

Reads the live OpenRouter catalogue, checks Hugging Face for published
weights, and writes
`docs/content/tasks/tool-use-correctness/open-weight-coverage.md`.

Open-weight status is *verified*, not assumed: for a fine-tuning decision a
guess is worse than nothing, and several of these models postdate any given
model's training data. A model counts as open only when its exact weights repo
resolves on Hugging Face.

Needs the network. Run it by hand when the upstream catalogue changes.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date

from llmsearchbench.paths import SITE_DOCS
from llmsearchbench.providers import MODELS

OPENROUTER = "https://openrouter.ai/api/v1/models"
HUGGINGFACE = "https://huggingface.co/api/models/"
PAGE = SITE_DOCS / "tasks" / "tool-use-correctness" / "open-weight-coverage.md"

#: Medians measured across the completed Qwen sweep, used to price a run for
#: models that have not been run. Output varied 18K to 343K, so this is a rough
#: figure and a thinking model will exceed it.
RUN_IN, RUN_OUT = 93_372, 87_235

#: Vendors this page covers, and the label to group them under.
VENDORS = {
    "openai": "GPT-OSS",
    "z-ai": "Z.ai (GLM)",
    "deepseek": "DeepSeek",
    "nvidia": "Nemotron",
    "thinkingmachines": "Thinking Machines",
    "moonshotai": "Kimi (Moonshot)",
    "minimax": "MiniMax",
    "xiaomi": "Xiaomi (MiMo)",
    "meta-llama": "Llama",
    "meta": "Meta (Muse)",
    "mistralai": "Mistral",
    "meituan": "Meituan (LongCat)",
    "tencent": "Tencent (Hunyuan)",
    "dots-studio": "DotsStudio",
    "sakana": "Sakana",
}

#: Providers reached directly rather than through OpenRouter, so they do not
#: appear in its catalogue and are described by hand.
DIRECT_PROVIDERS = """## Avey

Reached directly at `staging1.api.avey.ai`, not through OpenRouter.

| Model | Weights | Reasoning | Tools | Run? |
| --- | --- | --- | :---: | :---: |
| `avey/olive` | not published | yes, always on | **N** | blocked |

`avey/olive` **cannot run this benchmark as deployed.** Its vLLM server was
started without `--enable-auto-tool-choice` and `--tool-call-parser`, so any
request carrying `tools` is rejected with a 400. Every variant fails:
`tool_choice` omitted or `auto` errors, a forced function errors, and
`tool_choice: "none"` is accepted but by definition never calls the tool — which
is the thing being measured. The provider has to set those flags; there is no
client-side workaround.

The adapter and catalogue entry are in place, so the model runs the moment they
do. Avey publishes no price, so its cost figures would read zero and must not be
compared with a priced model.
"""

#: Exact Hugging Face repo for each OpenRouter id we have checked. Absence from
#: this map means "not checked", which the table reports honestly rather than
#: guessing.
WEIGHTS = {
    "openai/gpt-oss-20b": "openai/gpt-oss-20b",
    "openai/gpt-oss-120b": "openai/gpt-oss-120b",
    "openai/gpt-oss-safeguard-20b": "openai/gpt-oss-safeguard-20b",
    "z-ai/glm-4.7": "zai-org/GLM-4.7",
    "z-ai/glm-4.7-flash": "zai-org/GLM-4.7-Flash",
    "z-ai/glm-5": "zai-org/GLM-5",
    "z-ai/glm-5.2": "zai-org/GLM-5.2",
    "z-ai/glm-5.3": "zai-org/GLM-5.3",
    "z-ai/glm-5.3-flash": "zai-org/GLM-5.3-Flash",
    "z-ai/glm-4.5": "zai-org/GLM-4.5",
    "z-ai/glm-4.5-air": "zai-org/GLM-4.5-Air",
    "z-ai/glm-4.6": "zai-org/GLM-4.6",
    "deepseek/deepseek-r1": "deepseek-ai/DeepSeek-R1",
    "deepseek/deepseek-v3.2": "deepseek-ai/DeepSeek-V3.2",
    "deepseek/deepseek-v4-flash": "deepseek-ai/DeepSeek-V4-Flash",
    "deepseek/deepseek-v4-pro": "deepseek-ai/DeepSeek-V4-Pro",
    "deepseek/deepseek-v4.1-flash": "deepseek-ai/DeepSeek-V4.1-Flash",
    "nvidia/nemotron-3-nano-30b-a3b": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
    "nvidia/nemotron-3-super-120b-a12b": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16",
    "nvidia/nemotron-3-ultra-550b-a55b": "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16",
    "nvidia/nemotron-3.5-lightning": "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
    "thinkingmachines/inkling": "thinkingmachines/Inkling",
    "thinkingmachines/inkling-small": "thinkingmachines/Inkling-Small",
    "moonshotai/kimi-k2": "moonshotai/Kimi-K2-Instruct",
    "moonshotai/kimi-k2.5": "moonshotai/Kimi-K2.5",
    "moonshotai/kimi-k2.6": "moonshotai/Kimi-K2.6",
    "moonshotai/kimi-k2.7-code": "moonshotai/Kimi-K2.7-Code",
    "moonshotai/kimi-k3": "moonshotai/Kimi-K3",
    "minimax/minimax-m2": "MiniMaxAI/MiniMax-M2",
    "minimax/minimax-m2.5": "MiniMaxAI/MiniMax-M2.5",
    "minimax/minimax-m2.7": "MiniMaxAI/MiniMax-M2.7",
    "minimax/minimax-m3": "MiniMaxAI/MiniMax-M3",
    "minimax/minimax-m1": "MiniMaxAI/MiniMax-M1-80k",
    "xiaomi/mimo-v2.5": "XiaomiMiMo/MiMo-V2.5",
    "xiaomi/mimo-v2.5-pro": "XiaomiMiMo/MiMo-V2.5-Pro",
    "xiaomi/mimo-v2.6-flash": "XiaomiMiMo/MiMo-V2.6-Flash",
    "xiaomi/mimo-v2.6-pro": "XiaomiMiMo/MiMo-V2.6-Pro",
    "meta-llama/llama-3.1-8b-instruct": "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/llama-3.1-70b-instruct": "meta-llama/Llama-3.1-70B-Instruct",
    "meta-llama/llama-3.3-70b-instruct": "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/llama-4-scout": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "meta-llama/llama-4-maverick": "meta-llama/Llama-4-Maverick-17B-128E-Instruct",
    "meta/muse-glimmer-30b": "facebook/Muse-Glimmer-30B",
    "mistralai/mistral-nemo": "mistralai/Mistral-Nemo-Instruct-2407",
    "mistralai/mistral-small-3.2-24b-instruct": (
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    ),
    "mistralai/mistral-small-3.1-24b-instruct": (
        "mistralai/Mistral-Small-3.1-24B-Instruct-2503"
    ),
    "mistralai/mixtral-8x22b-instruct": "mistralai/Mixtral-8x22B-Instruct-v0.1",
    "mistralai/mistral-small-2603": "mistralai/Mistral-Small-2603",
    "mistralai/ministral-8b-2512": "mistralai/Ministral-8B-Instruct-2512",
    "mistralai/ministral-14b-2512": "mistralai/Ministral-14B-Instruct-2512",
    "mistralai/ministral-3b-2512": "mistralai/Ministral-3B-Instruct-2512",
    "mistralai/devstral-2512": "mistralai/Devstral-2512",
    "meituan/longcat-2.0": "meituan-longcat/LongCat-2.0",
    "tencent/hy3": "tencent/HY3",
    "tencent/hy4-preview": "tencent/HY4",
    "tencent/hunyuan-a13b-instruct": "tencent/Hunyuan-A13B-Instruct",
    "dots-studio/dots-3-note-preview": "rednote-hilab/dots3-note",
    "sakana/fugu-max": "SakanaAI/Fugu-Max",
    "sakana/sakana-namazu": "SakanaAI/Namazu",
}


def licence_of(repo: str) -> str | None:
    """The licence on a Hugging Face repo, or None when it does not exist."""
    try:
        with urllib.request.urlopen(HUGGINGFACE + repo, timeout=20) as response:
            model = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return (model.get("cardData") or {}).get("license") or "unstated"


def reasoning(supported: set[str]) -> str:
    if "reasoning_effort" in supported:
        return "effort levels"
    if "reasoning" in supported:
        return "on / off"
    return "none"


def main() -> None:
    with urllib.request.urlopen(OPENROUTER, timeout=30) as response:
        catalogue = json.load(response)["data"]

    ours = set(MODELS)
    # Kimi is catalogued against Moonshot's own API, under a different id.
    ours |= {
        "moonshotai/" + model_id.split("/", 1)[1]
        for model_id in MODELS
        if model_id.startswith("moonshot/")
    }

    licences: dict[str, str | None] = {}
    for model_id, repo in WEIGHTS.items():
        licences[model_id] = licence_of(repo)
        time.sleep(0.05)

    lines = [
        "---",
        "id: open-weight-coverage",
        "title: Open-weight coverage",
        "sidebar_position: 8",
        "description: Which open-weight models this benchmark has run, and which it has not.",
        "---",
        "",
        "<!-- Generated by `uv run python scripts/open_weight_coverage.py`. "
        "Do not edit by hand. -->",
        "",
        "# Open-weight coverage",
        "",
        f"As of {date.today().isoformat()}. Only models whose **weights are actually "
        "published** are candidates here — the point of this page is deciding what "
        "could be fine-tuned, and for that a guess is worse than nothing.",
        "",
        "Open-weight status is verified against Hugging Face at generation time, not "
        "assumed. A model counts as open only when its exact weights repository "
        "resolves.",
        "",
        "**Run cost** prices a full 360-item run from token counts measured on real "
        "runs. Output varied by a factor of nineteen across models, so treat it as an "
        "order of magnitude, not a quote.",
        "",
    ]

    for vendor, label in VENDORS.items():
        models = sorted(
            (m for m in catalogue if m["id"].split("/")[0] == vendor),
            key=lambda m: m["id"],
        )
        if vendor == "openai":
            models = [m for m in models if "oss" in m["id"]]
        if not models:
            lines += [f"## {label}", "", "Nothing from this vendor on OpenRouter.", ""]
            continue

        lines += [
            f"## {label}",
            "",
            "| Model | Weights | Licence | Reasoning | Tools | Run cost | Run? |",
            "| --- | --- | --- | --- | :---: | ---: | :---: |",
        ]
        for model in models:
            supported = set(model.get("supported_parameters") or [])
            pricing = model["pricing"]
            price_in = float(pricing["prompt"]) * 1e6
            price_out = float(pricing["completion"]) * 1e6
            run = RUN_IN / 1e6 * price_in + RUN_OUT / 1e6 * price_out

            model_id = model["id"]
            checked = model_id in licences
            licence = licences.get(model_id)
            if not checked:
                weights, licence_text = "not checked", "—"
            elif licence is None:
                weights, licence_text = "**no**", "—"
            else:
                weights, licence_text = "yes", licence

            has_tools = "tools" in supported
            if model_id in ours:
                mark = "**yes**"
            elif not has_tools:
                mark = "n/a"
            else:
                mark = "—"

            lines.append(
                f"| `{model_id.split('/', 1)[1]}` | {weights} | {licence_text} | "
                f"{reasoning(supported)} | {'y' if has_tools else 'N'} | "
                f"${run:.3f} | {mark} |"
            )
        lines.append("")

    lines += [DIRECT_PROVIDERS, ""]

    lines += [
        "## How a model gets on the run list",
        "",
        "Three gates, in order:",
        "",
        "1. **Weights published.** No repository on Hugging Face, no entry. This rules "
        "out Sakana's Fugu line, Meta's Muse line, Tencent's HY4, DotsStudio's dots-3, "
        "Xiaomi's v2.6 tier, and Mistral's commercial tier — all API-only.",
        "2. **Tool calling supported.** The benchmark *is* a tool call. Several "
        "open-weight models fail here, including Tencent's Hunyuan A13B and the "
        "DeepSeek R1 distills — and one whole provider, Avey, whose server has "
        "tool calling switched off.",
        "3. **Adds something.** One model per family per size tier. Vision and coder "
        "variants are skipped unless they answer a specific question — a coder model "
        "is included as a control, to see whether code tuning changes tool judgement.",
        "",
        "## Licences worth reading before fine-tuning",
        "",
        "A licence of `other` is not a red flag by itself, but it is not Apache or MIT "
        "either. Llama, Nemotron, MiniMax and Kimi all use custom terms with "
        "attribution or use restrictions. The unencumbered bases here are the "
        "Apache-2.0 and MIT rows.",
        "",
        "## Routing",
        "",
        "Kimi runs against **Moonshot's own API**, not OpenRouter, because a key for it "
        "was available. Its price in the results is the OpenRouter listing for the same "
        "weights, used as a proxy — Moonshot does not publish machine-readable pricing. "
        "A model called through different routes is not strictly comparable; the route "
        "is recorded with every run.",
        "",
    ]

    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text("\n".join(lines), encoding="utf-8")
    ran = sum(1 for m in catalogue if m["id"] in ours)
    print(f"wrote {PAGE}  ({ran} model(s) marked as run)")


if __name__ == "__main__":
    main()
