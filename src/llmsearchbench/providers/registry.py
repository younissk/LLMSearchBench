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
            price_in_per_mtok=0.0,
            price_out_per_mtok=0.0,
            priced_on="",
            notes="prices not filled in yet",
        ),
        ModelSpec(
            id="claude-sonnet-5",
            label="Claude Sonnet 5",
            provider="anthropic",
            price_in_per_mtok=0.0,
            price_out_per_mtok=0.0,
            priced_on="",
            notes="prices not filled in yet",
        ),
        ModelSpec(
            id="claude-haiku-4-5-20251001",
            label="Claude Haiku 4.5",
            provider="anthropic",
            price_in_per_mtok=0.0,
            price_out_per_mtok=0.0,
            priced_on="",
            notes="prices not filled in yet",
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
        if model.price_in_per_mtok <= 0 and model.price_out_per_mtok <= 0
    ]
