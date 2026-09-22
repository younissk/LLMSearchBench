"""Who serves which model, and what it costs.

* `entities` - what a provider and a model are
* `registry` - the catalogue itself, and the lookups over it
"""

from llmsearchbench.providers.entities import ModelSpec, Provider
from llmsearchbench.providers.registry import (
    MODELS,
    PROVIDERS,
    UnknownModelError,
    get_model,
    get_provider,
    models_without_prices,
    provider_label,
)

__all__ = [
    "MODELS",
    "PROVIDERS",
    "ModelSpec",
    "Provider",
    "UnknownModelError",
    "get_model",
    "get_provider",
    "models_without_prices",
    "provider_label",
]
