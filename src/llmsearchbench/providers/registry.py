"""The catalogue: who serves which model, and at what price.

Adding a model here is the only place a new model needs registering; the CLI,
the cost calculation, and the results table all read from this one dict.
"""

from __future__ import annotations

from llmsearchbench.providers.entities import ModelSpec, Provider

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
    """Models that would publish a cost of zero. Checked before a release."""
    return [
        model
        for model in MODELS.values()
        if not model.is_free and model.price_in_per_mtok <= 0 and model.price_out_per_mtok <= 0
    ]
