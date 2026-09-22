"""The Python models and the documentation site's TypeScript are the same schema
written twice. These tests are the thing that keeps them in step.

Python keeps snake_case attributes and carries a camelCase alias; the alias is
what lands in JSON, so the alias is what must match the TypeScript.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from llmsearchbench.storage import load_summary, save_summary
from llmsearchbench.types import ResultRow, Summary

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_TYPES = REPO_ROOT / "docs" / "src" / "data" / "types.ts"
SITE_RELEASES = REPO_ROOT / "docs" / "src" / "data" / "releases"

FRACTION_FIELDS = ("accuracy", "citation_f1", "hallucination_rate")


def _typescript_fields(source: str, interface: str) -> set[str]:
    """Pull the property names out of one TypeScript interface body."""
    match = re.search(rf"interface\s+{interface}\s*{{(.*?)\n}}", source, re.DOTALL)
    if match is None:
        raise AssertionError(f"interface {interface} not found in {SITE_TYPES}")
    body = re.sub(r"/\*\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return set(re.findall(r"^\s*(\w+)\??:", body, re.MULTILINE))


def _json_names(model: type[ResultRow] | type[Summary]) -> set[str]:
    """The keys this model actually writes — the alias where one is set."""
    return {field.alias or name for name, field in model.model_fields.items()}


@pytest.fixture(scope="module")
def site_types_source() -> str:
    return SITE_TYPES.read_text(encoding="utf-8")


class TestSchemaParity:
    def test_result_row_json_keys_match_the_site(self, site_types_source: str) -> None:
        assert _json_names(ResultRow) == _typescript_fields(site_types_source, "ResultRow")

    def test_summary_json_keys_match_the_site(self, site_types_source: str) -> None:
        assert _json_names(Summary) == _typescript_fields(site_types_source, "Release")

    def test_the_cost_alias_is_not_the_generated_one(self) -> None:
        """`to_camel` produces `costPer1K`; the site reads `costPer1k`."""
        assert ResultRow.model_fields["cost_per_1k"].alias == "costPer1k"

    def test_python_attributes_stay_snake_case(self) -> None:
        assert all(name == name.lower() for name in ResultRow.model_fields)


class TestShippedReleases:
    @pytest.mark.parametrize("path", sorted(SITE_RELEASES.glob("*.json")), ids=lambda p: p.stem)
    def test_every_published_release_parses(self, path: Path) -> None:
        summary = load_summary(path)
        assert summary.version == path.stem
        assert summary.rows

    @pytest.mark.parametrize("path", sorted(SITE_RELEASES.glob("*.json")), ids=lambda p: p.stem)
    def test_fractions_are_fractions_not_percentages(self, path: Path) -> None:
        """87.1 instead of 0.871 would render as 8710% — the type now refuses it."""
        for row in load_summary(path).rows:
            for metric in FRACTION_FIELDS:
                assert 0.0 <= float(getattr(row, metric)) <= 1.0

    @pytest.mark.parametrize("path", sorted(SITE_RELEASES.glob("*.json")), ids=lambda p: p.stem)
    def test_round_trips_without_losing_a_field(self, path: Path) -> None:
        """Writing a release back must not drop anything the site reads."""
        original = json.loads(path.read_text(encoding="utf-8"))
        assert load_summary(path).model_dump(exclude_none=True) == original

    @pytest.mark.parametrize("path", sorted(SITE_RELEASES.glob("*.json")), ids=lambda p: p.stem)
    def test_rewriting_is_byte_identical(self, path: Path, tmp_path: Path) -> None:
        """`make publish` must not reformat a release it did not change."""
        target = tmp_path / path.name
        save_summary(target, load_summary(path))
        assert target.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")

    def test_no_model_appears_twice_in_a_release(self) -> None:
        for path in SITE_RELEASES.glob("*.json"):
            models = [row.model for row in load_summary(path).rows]
            assert len(models) == len(set(models))
