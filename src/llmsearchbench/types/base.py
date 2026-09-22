"""Shared model configuration.

Two shapes of JSON live in this project, and they do not agree on naming:

* the run artefacts we write for ourselves (`raw.jsonl`, `manifest.json`) are
  snake_case, matching the Python that produces them;
* the files the documentation site reads (`summary.json`) are camelCase,
  because the site is TypeScript.

Rather than spell camelCase field names in Python — which cost us a `noqa` on
every one — the site-facing models keep snake_case attributes and carry an
alias. Pydantic serialises by alias, so the JSON on disk is unchanged.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BenchModel(BaseModel):
    """Base for records we read and write in snake_case.

    `extra="forbid"` is deliberate: a typo'd key in an artefact should fail
    loudly at load, not silently vanish and take a metric with it.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class SiteModel(BaseModel):
    """Base for records the documentation site reads, which are camelCase.

    Accepts either spelling on input (`populate_by_name`) and always writes the
    camelCase alias, so `docs/src/data/types.ts` stays the contract.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )
