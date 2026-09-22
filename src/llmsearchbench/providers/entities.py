"""What a provider and a model under test are.

Prices are USD per million tokens at list, and they are part of a release\'s
identity: `costPer1k` on the published table is computed from whatever the
catalogue holds at run time, so a price edit changes published numbers.
"""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types import BenchModel


class Provider(BenchModel):
    """An API that serves models under test."""

    key: str = Field(min_length=1)
    #: Shown in the results table and used to colour the charts.
    label: str = Field(min_length=1)
    #: Environment variable holding the credential, read from `.env`.
    env_var: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    docs_url: str = Field(pattern=r"^https://")


class ModelSpec(BenchModel):
    """One model under test, pinned to an exact API id."""

    #: The id sent to the API. Pinning a dated snapshot is what makes a run repeatable.
    id: str = Field(min_length=1)
    #: Shown in the results table.
    label: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    price_in_per_mtok: float = Field(ge=0)
    price_out_per_mtok: float = Field(ge=0)
    #: ISO date the prices above were last checked. A price with no date cannot
    #: be re-checked, and prices move.
    priced_on: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    #: False for models that ignore `temperature`; those are run three times
    #: and the modal verdict is taken.
    supports_temperature: bool = True
    notes: str = ""
