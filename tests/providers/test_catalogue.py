"""The model and provider catalogue."""

from __future__ import annotations

import pytest

from llmsearchbench.providers import (
    MODELS,
    PROVIDERS,
    UnknownModelError,
    get_model,
    get_provider,
    models_without_prices,
    provider_label,
)


class TestLookup:
    def test_known_model(self) -> None:
        assert get_model("claude-opus-5").label == "Claude Opus 5"

    def test_unknown_model_lists_what_is_known(self) -> None:
        with pytest.raises(UnknownModelError, match="claude-opus-5"):
            get_model("gpt-nonexistent")

    def test_unknown_provider_lists_what_is_known(self) -> None:
        with pytest.raises(KeyError, match="anthropic"):
            get_provider("not-a-provider")

    def test_provider_label_is_what_the_results_table_shows(self) -> None:
        assert provider_label("claude-opus-5") == "Anthropic"


class TestCatalogueIntegrity:
    def test_every_model_points_at_a_registered_provider(self) -> None:
        for model in MODELS.values():
            assert model.provider in PROVIDERS, f"{model.id} has provider {model.provider!r}"

    def test_every_provider_declares_a_credential_variable(self) -> None:
        for provider in PROVIDERS.values():
            assert provider.env_var.isupper()

    def test_model_keys_match_their_ids(self) -> None:
        """The dict key is the string sent to the API; a mismatch runs the wrong model."""
        for key, model in MODELS.items():
            assert key == model.id

    def test_labels_are_unique(self) -> None:
        """Two rows with the same label would be indistinguishable on the results table."""
        labels = [model.label for model in MODELS.values()]
        assert len(labels) == len(set(labels))

    def test_a_priced_model_records_when_it_was_priced(self) -> None:
        """A price with no date cannot be re-checked, and prices move."""
        for model in MODELS.values():
            if model.price_in_per_mtok > 0 or model.price_out_per_mtok > 0:
                assert model.priced_on, f"{model.id} has prices but no priced_on date"


class TestPricingGate:
    def test_every_catalogued_model_has_a_price(self) -> None:
        """Publishing a cost of zero would be a lie, so a release checks this first.

        A free endpoint or a provider that publishes no price is exempt; both
        say so on the model itself.
        """
        assert models_without_prices() == []

    def test_model_ids_carry_no_date_suffix(self) -> None:
        """Dated snapshot ids are not the published model strings."""
        for model_id in MODELS:
            assert not model_id[-8:].isdigit(), f"{model_id} looks date-suffixed"


class TestUnpricedProviders:
    def test_a_price_unknown_model_does_not_trip_the_pricing_gate(self) -> None:
        """Avey publishes no price; that is different from a forgotten one."""
        from llmsearchbench.providers import MODELS, models_without_prices

        unknown = [m for m in MODELS.values() if m.price_unknown]
        assert unknown, "expected at least one price-unknown model"
        assert not any(m.price_unknown for m in models_without_prices())

    def test_a_price_unknown_model_says_so_in_its_notes(self) -> None:
        from llmsearchbench.providers import MODELS

        for model in MODELS.values():
            if model.price_unknown:
                assert "price" in model.notes.lower()
