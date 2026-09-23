"""The catalogue: who serves which model, and at what price.

Adding a model here is the only place a new model needs registering; the CLI,
the cost calculation, and the results table all read from this one dict.
"""

from __future__ import annotations

from llmsearchbench.providers.entities import ModelSpec, Provider
from llmsearchbench.types.enums import ToolProtocol

PROVIDERS: dict[str, Provider] = {
    provider.key: provider
    for provider in (
        Provider(
            key="anthropic",
            label="Anthropic",
            env_var="ANTHROPIC_API_KEY",
            docs_url="https://docs.anthropic.com/en/api/overview",
        ),
        Provider(
            key="openai",
            label="OpenAI",
            env_var="OPENAI_API_KEY",
            docs_url="https://platform.openai.com/docs/api-reference",
        ),
        Provider(
            key="google",
            label="Google",
            env_var="GOOGLE_API_KEY",
            docs_url="https://ai.google.dev/gemini-api/docs",
        ),
        Provider(
            key="openrouter",
            label="OpenRouter",
            env_var="OPENROUTER_API_KEY",
            docs_url="https://openrouter.ai/docs",
        ),
        Provider(
            key="avey",
            label="Avey",
            env_var="AVEY_API_KEY",
            docs_url="https://staging1.api.avey.ai",
        ),
        Provider(
            key="moonshot",
            label="Moonshot",
            env_var="KIMI_API_KEY",
            docs_url="https://platform.moonshot.ai/docs",
        ),
        Provider(
            key="local",
            label="Local",
            env_var="LOCAL_MODEL_BASE_URL",
            docs_url="https://github.com/ggml-org/llama.cpp",
        ),
    )
}


MODELS: dict[str, ModelSpec] = {
    model.id: model
    for model in (
        ModelSpec(
            id="claude-opus-5",
            label="Claude Opus 5",
            provider="anthropic",
            price_in_per_mtok=5.00,
            price_out_per_mtok=25.00,
            priced_on="2026-09-22",
            supports_temperature=False,
            notes="sampling parameters are rejected; thinking is on by default",
        ),
        ModelSpec(
            id="claude-sonnet-5",
            label="Claude Sonnet 5",
            provider="anthropic",
            price_in_per_mtok=2.00,
            price_out_per_mtok=10.00,
            priced_on="2026-09-22",
            supports_temperature=False,
            notes="sampling parameters are rejected",
        ),
        ModelSpec(
            id="claude-haiku-4-5",
            label="Claude Haiku 4.5",
            provider="anthropic",
            price_in_per_mtok=1.00,
            price_out_per_mtok=5.00,
            priced_on="2026-09-22",
            supports_temperature=True,
        ),
        # Routed through OpenRouter: one key, many providers. The id is
        # OpenRouter's, and a run's manifest records the route — a model called
        # through OpenRouter is not strictly comparable to the same model called
        # first-party.
        ModelSpec(
            id="openai/gpt-oss-20b",
            label="GPT-OSS 20B",
            provider="openrouter",
            price_in_per_mtok=0.0180,
            price_out_per_mtok=0.0900,
            priced_on="2026-09-23",
            notes="Apache-2.0 weights",
        ),
        ModelSpec(
            id="openai/gpt-oss-120b",
            label="GPT-OSS 120B",
            provider="openrouter",
            price_in_per_mtok=0.1500,
            price_out_per_mtok=0.6000,
            priced_on="2026-09-23",
            notes="Apache-2.0 weights",
        ),
        ModelSpec(
            id="z-ai/glm-4.7-flash",
            label="GLM-4.7 Flash",
            provider="openrouter",
            price_in_per_mtok=0.0605,
            price_out_per_mtok=0.4000,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="z-ai/glm-5.3-flash",
            label="GLM-5.3 Flash",
            provider="openrouter",
            price_in_per_mtok=0.1500,
            price_out_per_mtok=0.5000,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="z-ai/glm-5",
            label="GLM-5",
            provider="openrouter",
            price_in_per_mtok=0.6000,
            price_out_per_mtok=1.9200,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="deepseek/deepseek-v4-flash",
            label="DeepSeek V4 Flash",
            provider="openrouter",
            price_in_per_mtok=0.0886,
            price_out_per_mtok=0.1772,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="deepseek/deepseek-v3.2",
            label="DeepSeek V3.2",
            provider="openrouter",
            price_in_per_mtok=0.2690,
            price_out_per_mtok=0.4000,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="deepseek/deepseek-r1",
            label="DeepSeek R1",
            provider="openrouter",
            price_in_per_mtok=0.7000,
            price_out_per_mtok=2.5000,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="nvidia/nemotron-3-nano-30b-a3b",
            label="Nemotron 3 Nano 30B-A3B",
            provider="openrouter",
            price_in_per_mtok=0.0500,
            price_out_per_mtok=0.2000,
            priced_on="2026-09-23",
            notes="NVIDIA open model licence",
        ),
        ModelSpec(
            id="nvidia/nemotron-3-super-120b-a12b",
            label="Nemotron 3 Super 120B-A12B",
            provider="openrouter",
            price_in_per_mtok=0.0800,
            price_out_per_mtok=0.4500,
            priced_on="2026-09-23",
            notes="NVIDIA open model licence",
        ),
        ModelSpec(
            id="thinkingmachines/inkling-small",
            label="Inkling Small",
            provider="openrouter",
            price_in_per_mtok=0.4500,
            price_out_per_mtok=1.2000,
            priced_on="2026-09-23",
            notes="Apache-2.0 weights",
        ),
        ModelSpec(
            id="thinkingmachines/inkling",
            label="Inkling",
            provider="openrouter",
            price_in_per_mtok=1.0000,
            price_out_per_mtok=4.0500,
            priced_on="2026-09-23",
            notes="Apache-2.0 weights",
        ),
        ModelSpec(
            id="minimax/minimax-m2",
            label="MiniMax M2",
            provider="openrouter",
            price_in_per_mtok=0.2550,
            price_out_per_mtok=1.0200,
            priced_on="2026-09-23",
            notes="open weights",
        ),
        ModelSpec(
            id="minimax/minimax-m3",
            label="MiniMax M3",
            provider="openrouter",
            price_in_per_mtok=0.3000,
            price_out_per_mtok=1.2000,
            priced_on="2026-09-23",
            notes="open weights",
        ),
        ModelSpec(
            id="xiaomi/mimo-v2.5",
            label="MiMo V2.5",
            provider="openrouter",
            price_in_per_mtok=0.1400,
            price_out_per_mtok=0.2800,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="xiaomi/mimo-v2.5-pro",
            label="MiMo V2.5 Pro",
            provider="openrouter",
            price_in_per_mtok=0.4350,
            price_out_per_mtok=0.8700,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="meta-llama/llama-3.3-70b-instruct",
            label="Llama 3.3 70B",
            provider="openrouter",
            price_in_per_mtok=0.1000,
            price_out_per_mtok=0.3200,
            priced_on="2026-09-23",
            notes="Llama licence; no reasoning mode",
        ),
        ModelSpec(
            id="meta-llama/llama-3.1-8b-instruct",
            label="Llama 3.1 8B",
            provider="openrouter",
            price_in_per_mtok=0.0500,
            price_out_per_mtok=0.0800,
            priced_on="2026-09-23",
            notes="Llama licence; no reasoning mode",
        ),
        ModelSpec(
            id="mistralai/mistral-small-3.2-24b-instruct",
            label="Mistral Small 3.2 24B",
            provider="openrouter",
            price_in_per_mtok=0.0938,
            price_out_per_mtok=0.2500,
            priced_on="2026-09-23",
            notes="Apache-2.0 weights",
        ),
        ModelSpec(
            id="mistralai/mistral-nemo",
            label="Mistral Nemo 12B",
            provider="openrouter",
            price_in_per_mtok=0.0190,
            price_out_per_mtok=0.0300,
            priced_on="2026-09-23",
            notes="Apache-2.0 weights",
        ),
        ModelSpec(
            id="meituan/longcat-2.0",
            label="LongCat 2.0",
            provider="openrouter",
            price_in_per_mtok=0.3000,
            price_out_per_mtok=1.2000,
            priced_on="2026-09-23",
            notes="MIT weights",
        ),
        ModelSpec(
            id="tencent/hy3",
            label="Hunyuan HY3",
            provider="openrouter",
            price_in_per_mtok=0.1320,
            price_out_per_mtok=0.5280,
            priced_on="2026-09-23",
            notes="Apache-2.0 weights",
        ),
        ModelSpec(
            id="moonshot/kimi-k2.6",
            label="Kimi K2.6",
            provider="moonshot",
            price_in_per_mtok=0.9500,
            price_out_per_mtok=4.0000,
            priced_on="2026-09-23",
            supports_temperature=False,
            notes=(
                "open weights; price is the OpenRouter listing, used as a proxy. "
                "Moonshot rejects any temperature but 1, so none is sent."
            ),
        ),
        ModelSpec(
            id="moonshot/kimi-k3",
            label="Kimi K3",
            provider="moonshot",
            price_in_per_mtok=3.0000,
            price_out_per_mtok=15.0000,
            priced_on="2026-09-23",
            supports_temperature=False,
            notes=(
                "open weights; price is the OpenRouter listing, used as a proxy. "
                "Moonshot rejects any temperature but 1, so none is sent."
            ),
        ),
        ModelSpec(
            id="avey/olive",
            label="Avey Olive",
            provider="avey",
            price_in_per_mtok=0.0,
            price_out_per_mtok=0.0,
            priced_on="",
            price_unknown=True,
            tool_protocol=ToolProtocol.PROMPTED,
            notes=(
                "the provider's vLLM server has tool calling disabled, so the "
                "tool is described in the prompt and the call is parsed out of "
                "the reply. Not comparable to a native tool-calling run. Avey "
                "publishes no price, so cost reads zero."
            ),
        ),
        # Add more OpenRouter models here with their listed prices from
        # openrouter.ai/models. A model with no price cannot be published:
        # `models_without_prices()` is what a release checks.
        ModelSpec(
            id="qwen/qwen-2.5-7b-instruct",
            label="Qwen2.5 7B",
            provider="openrouter",
            price_in_per_mtok=0.1000,
            price_out_per_mtok=0.2000,
            priced_on="2026-09-22",
            notes="smallest catalogued Qwen",
        ),
        ModelSpec(
            id="qwen/qwen-2.5-72b-instruct",
            label="Qwen2.5 72B",
            provider="openrouter",
            price_in_per_mtok=0.3600,
            price_out_per_mtok=0.4000,
            priced_on="2026-09-22",
            notes="pre-reasoning baseline",
        ),
        ModelSpec(
            id="qwen/qwen3-8b",
            label="Qwen3 8B",
            provider="openrouter",
            price_in_per_mtok=0.1170,
            price_out_per_mtok=0.4550,
            priced_on="2026-09-22",
        ),
        ModelSpec(
            id="qwen/qwen3-32b",
            label="Qwen3 32B",
            provider="openrouter",
            price_in_per_mtok=0.0800,
            price_out_per_mtok=0.2800,
            priced_on="2026-09-22",
            notes="first generation with a reasoning mode",
        ),
        ModelSpec(
            id="qwen/qwen3-30b-a3b-instruct-2507",
            label="Qwen3 30B-A3B Instruct",
            provider="openrouter",
            price_in_per_mtok=0.0481,
            price_out_per_mtok=0.1930,
            priced_on="2026-09-22",
            notes="instruct half of a thinking/instruct pair",
        ),
        ModelSpec(
            id="qwen/qwen3-30b-a3b-thinking-2507",
            label="Qwen3 30B-A3B Thinking",
            provider="openrouter",
            price_in_per_mtok=0.2000,
            price_out_per_mtok=2.4000,
            priced_on="2026-09-22",
            notes="thinking half of a thinking/instruct pair",
        ),
        ModelSpec(
            id="qwen/qwen3-235b-a22b-2507",
            label="Qwen3 235B-A22B Instruct",
            provider="openrouter",
            price_in_per_mtok=0.0875,
            price_out_per_mtok=0.3500,
            priced_on="2026-09-22",
            notes="instruct half of a thinking/instruct pair",
        ),
        ModelSpec(
            id="qwen/qwen3-235b-a22b-thinking-2507",
            label="Qwen3 235B-A22B Thinking",
            provider="openrouter",
            price_in_per_mtok=0.2300,
            price_out_per_mtok=2.3000,
            priced_on="2026-09-22",
            notes="thinking half of a thinking/instruct pair",
        ),
        ModelSpec(
            id="qwen/qwen3-coder-30b-a3b-instruct",
            label="Qwen3 Coder 30B-A3B",
            provider="openrouter",
            price_in_per_mtok=0.0700,
            price_out_per_mtok=0.2800,
            priced_on="2026-09-22",
            notes="control: does code tuning affect tool judgement",
        ),
        ModelSpec(
            id="qwen/qwen3.5-9b",
            label="Qwen3.5 9B",
            provider="openrouter",
            price_in_per_mtok=0.1000,
            price_out_per_mtok=0.1500,
            priced_on="2026-09-22",
        ),
        ModelSpec(
            id="qwen/qwen3.5-122b-a10b",
            label="Qwen3.5 122B-A10B",
            provider="openrouter",
            price_in_per_mtok=0.2600,
            price_out_per_mtok=2.0800,
            priced_on="2026-09-22",
        ),
        ModelSpec(
            id="qwen/qwen3.5-397b-a17b",
            label="Qwen3.5 397B-A17B",
            provider="openrouter",
            price_in_per_mtok=0.5500,
            price_out_per_mtok=3.5000,
            priced_on="2026-09-22",
        ),
        ModelSpec(
            id="qwen/qwen3.6-27b",
            label="Qwen3.6 27B",
            provider="openrouter",
            price_in_per_mtok=0.3200,
            price_out_per_mtok=2.7000,
            priced_on="2026-09-22",
        ),
        ModelSpec(
            id="qwen/qwen3.8-27b",
            label="Qwen3.8 27B",
            provider="openrouter",
            price_in_per_mtok=0.4200,
            price_out_per_mtok=3.0000,
            priced_on="2026-09-22",
        ),
        ModelSpec(
            id="qwen/qwen3.8-27b:free",
            label="Qwen3.8 27B (free tier)",
            provider="openrouter",
            price_in_per_mtok=0.0000,
            price_out_per_mtok=0.0000,
            priced_on="2026-09-22",
            is_free=True,
            notes="same weights as qwen3.8-27b, free endpoint",
        ),
        ModelSpec(
            id="qwen/qwen3.5-27b",
            label="Qwen3.5 27B",
            provider="openrouter",
            price_in_per_mtok=0.195,
            price_out_per_mtok=1.560,
            priced_on="2026-09-22",
            supports_temperature=True,
            notes="a thinking model; output tokens include reasoning",
        ),
        ModelSpec(
            id="anthropic/claude-sonnet-5",
            label="Claude Sonnet 5 (OpenRouter)",
            provider="openrouter",
            price_in_per_mtok=2.00,
            price_out_per_mtok=10.00,
            priced_on="2026-09-22",
            supports_temperature=False,
        ),
    )
}


class UnknownModelError(KeyError):
    """Raised for a model id that is not in the catalogue."""


def get_model(model_id: str) -> ModelSpec:
    try:
        return MODELS[model_id]
    except KeyError:
        known = ", ".join(sorted(MODELS)) or "(the catalogue is empty)"
        raise UnknownModelError(
            f"unknown model {model_id!r}. Known ids: {known}. "
            "Add it to MODELS in src/llmsearchbench/providers/registry.py."
        ) from None


def get_provider(key: str) -> Provider:
    try:
        return PROVIDERS[key]
    except KeyError:
        known = ", ".join(sorted(PROVIDERS))
        raise KeyError(f"unknown provider {key!r}. Known: {known}.") from None


def provider_label(model_id: str) -> str:
    """The provider label the results table shows for a model."""
    return get_provider(get_model(model_id).provider).label


def models_without_prices() -> list[ModelSpec]:
    """Models whose price was forgotten, which would publish a cost of zero.

    Free endpoints and providers that publish no price are excluded: a zero
    there is a fact, not an omission. Both are flagged on the model itself.
    """
    return [
        model
        for model in MODELS.values()
        if not model.is_free
        and not model.price_unknown
        and model.price_in_per_mtok <= 0
        and model.price_out_per_mtok <= 0
    ]
