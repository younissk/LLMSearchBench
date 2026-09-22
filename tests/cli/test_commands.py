"""Command line behaviour: exit codes and the messages someone acts on.

Driven through Typer's CliRunner, so these exercise the real argument parsing
and the real Rich rendering rather than calling the command functions directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llmsearchbench.cli import app
from llmsearchbench.storage import save_summary
from tests.conftest import make_row, make_summary

runner = CliRunner()


@pytest.fixture(autouse=True)
def wide_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rich wraps to the terminal width; pin it so assertions do not depend on it."""
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("TERM", "dumb")


class TestDiffCommand:
    def test_matching_summaries_exit_zero(self, tmp_path: Path) -> None:
        path = tmp_path / "summary.json"
        save_summary(path, make_summary())
        result = runner.invoke(app, ["diff", str(path), str(path)])
        assert result.exit_code == 0
        assert "match" in result.stdout

    def test_a_failed_reproduction_exits_nonzero(self, tmp_path: Path) -> None:
        """CI has to be able to gate on this."""
        actual = tmp_path / "actual.json"
        reference = tmp_path / "reference.json"
        save_summary(actual, make_summary(make_row(accuracy=0.50)))
        save_summary(reference, make_summary(make_row(accuracy=0.90)))

        result = runner.invoke(app, ["diff", str(actual), str(reference)])
        assert result.exit_code == 1
        assert "Out of tolerance" in result.stdout
        assert "accuracy" in result.stdout

    def test_a_missing_model_is_named(self, tmp_path: Path) -> None:
        actual = tmp_path / "actual.json"
        reference = tmp_path / "reference.json"
        save_summary(actual, make_summary(make_row("a")))
        save_summary(reference, make_summary(make_row("a"), make_row("b")))

        result = runner.invoke(app, ["diff", str(actual), str(reference)])
        assert result.exit_code == 1
        assert "missing" in result.stdout


class TestValidateCommand:
    def test_a_sane_summary_passes(self, tmp_path: Path) -> None:
        path = tmp_path / "summary.json"
        save_summary(path, make_summary())
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 0
        assert "valid" in result.stdout

    def test_an_out_of_range_metric_fails_and_names_the_field(self, tmp_path: Path) -> None:
        """Accuracy is a fraction; 87.1 means someone published percentages."""
        path = tmp_path / "summary.json"
        raw = make_summary().model_dump(exclude_none=True)
        raw["rows"][0]["accuracy"] = 87.1
        path.write_text(json.dumps(raw), encoding="utf-8")

        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 1
        assert "rows.0.accuracy" in result.stderr

    def test_a_duplicate_model_row_fails(self, tmp_path: Path) -> None:
        """Two rows for one model render as two indistinguishable lines."""
        path = tmp_path / "summary.json"
        raw = make_summary().model_dump(exclude_none=True)
        raw["rows"].append(dict(raw["rows"][0]))
        path.write_text(json.dumps(raw), encoding="utf-8")

        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 1
        assert "duplicate model rows" in result.stderr

    def test_placeholder_data_warns_but_does_not_fail(self, tmp_path: Path) -> None:
        path = tmp_path / "summary.json"
        raw = make_summary().model_dump(exclude_none=True)
        raw["placeholder"] = True
        path.write_text(json.dumps(raw), encoding="utf-8")

        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 0
        assert "placeholder" in result.stderr

    def test_a_missing_field_is_named(self, tmp_path: Path) -> None:
        path = tmp_path / "summary.json"
        path.write_text(json.dumps({"version": "v0.1.0"}), encoding="utf-8")

        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 1
        assert "date" in result.stderr

    def test_an_unexpected_key_is_rejected(self, tmp_path: Path) -> None:
        """A typo'd key should fail at load, not silently drop a metric."""
        path = tmp_path / "summary.json"
        raw = make_summary().model_dump(exclude_none=True)
        raw["rows"][0]["acccuracy"] = 0.5
        path.write_text(json.dumps(raw), encoding="utf-8")

        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 1
        assert "acccuracy" in result.stderr


class TestPublishCommand:
    def test_writes_into_the_site_and_says_what_is_still_manual(self, tmp_path: Path) -> None:
        source = tmp_path / "summary.json"
        site = tmp_path / "site"
        save_summary(source, make_summary(version="v0.3.0"))

        result = runner.invoke(app, ["publish", str(source), "--site", str(site)])
        assert result.exit_code == 0
        assert (site / "src" / "data" / "releases" / "v0.3.0.json").exists()
        assert "index.ts" in result.stdout


class TestRunCommand:
    @staticmethod
    def _write_task_set(directory: Path) -> None:
        (directory / "v0.1.0.jsonl").write_text(
            json.dumps(
                {
                    "id": "t-001",
                    "question": "q",
                    "gold_answer": "a",
                    "gold_sources": [],
                    "category": "negative",
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_a_missing_task_set_exits_two(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["run", "--release", "v9.9.9", "--model", "x", "--tasks-dir", str(tmp_path)],
        )
        assert result.exit_code == 2
        assert "no task set" in result.stderr

    def test_a_catalogued_model_with_no_adapter_says_where_to_wire_it(
        self, tmp_path: Path
    ) -> None:
        """Failing loudly beats silently substituting a different model."""
        self._write_task_set(tmp_path)
        result = runner.invoke(
            app,
            [
                "run",
                "--release",
                "v0.1.0",
                "--model",
                "claude-opus-5",
                "--tasks-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 3
        assert "adapters.py" in result.stderr

    def test_a_model_outside_the_catalogue_exits_two(self, tmp_path: Path) -> None:
        """A typo in a model id must not look like a missing adapter."""
        self._write_task_set(tmp_path)
        result = runner.invoke(
            app,
            [
                "run",
                "--release",
                "v0.1.0",
                "--model",
                "claude-opus-4",
                "--tasks-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 2
        assert "unknown model" in result.stderr

    def test_a_subset_run_says_it_is_not_a_valid_result(self, tmp_path: Path) -> None:
        self._write_task_set(tmp_path)
        result = runner.invoke(
            app,
            [
                "run",
                "--release",
                "v0.1.0",
                "--model",
                "claude-opus-5",
                "--tasks-dir",
                str(tmp_path),
                "--tasks",
                "1",
            ],
        )
        assert "not a valid result" in result.stderr


class TestAggregateCommand:
    @staticmethod
    def _write_records(path: Path, count: int) -> None:
        path.write_text(
            "\n".join(
                json.dumps(
                    {
                        "task_id": f"t-{i:03d}",
                        "model": "m",
                        "answer": "a",
                        "citations": [],
                        "verdict": "correct",
                        "tokens_in": 1,
                        "tokens_out": 1,
                        "latency_s": 1.0,
                        "search_calls": 1,
                    }
                )
                for i in range(count)
            )
            + "\n",
            encoding="utf-8",
        )

    def test_reports_what_it_read_before_failing_on_missing_prices(
        self, tmp_path: Path
    ) -> None:
        raw = tmp_path / "raw.jsonl"
        self._write_records(raw, 3)
        result = runner.invoke(app, ["aggregate", "--release", "v0.1.0", "--raw", str(raw)])
        assert result.exit_code == 3
        assert "3 records" in result.stdout
        assert "providers/registry.py" in result.stderr

    def test_an_empty_raw_file_exits_two(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw.jsonl"
        raw.write_text("", encoding="utf-8")
        result = runner.invoke(app, ["aggregate", "--release", "v0.1.0", "--raw", str(raw)])
        assert result.exit_code == 2
        assert "no records" in result.stderr


class TestModelsCommand:
    def test_lists_the_catalogue(self) -> None:
        result = runner.invoke(app, ["models"])
        assert result.exit_code == 0
        assert "claude-opus-5" in result.stdout

    def test_marks_models_that_would_publish_a_cost_of_zero(self) -> None:
        result = runner.invoke(app, ["models"])
        assert "UNPRICED" in result.stdout


class TestDataCommand:
    def test_list_shows_the_registry(self) -> None:
        result = runner.invoke(app, ["data", "list"])
        assert result.exit_code == 0
        assert "retrievalqa" in result.stdout
        assert "MIT" in result.stdout

    def test_verify_reports_missing_files_and_exits_nonzero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["data", "verify", "--root", str(tmp_path)])
        assert result.exit_code == 1
        assert "missing" in result.stdout
        assert "make data" in result.stderr

    def test_an_unknown_dataset_key_exits_two(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["data", "verify", "--dataset", "nope", "--root", str(tmp_path)]
        )
        assert result.exit_code == 2
        assert "unknown dataset" in result.stderr

    def test_download_reports_what_it_fetched_and_what_it_already_had(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from llmsearchbench.cli import data as data_cli
        from llmsearchbench.datasets import DatasetSpec, DownloadResult

        def fake_download(
            spec: DatasetSpec, *, root: Path, force: bool = False, **kwargs: object
        ) -> list[DownloadResult]:
            return [
                DownloadResult(
                    dataset=spec.key,
                    file=spec.files[0].name,
                    path=root / spec.files[0].name,
                    skipped=True,
                ),
                DownloadResult(
                    dataset=spec.key,
                    file=spec.files[1].name,
                    path=root / spec.files[1].name,
                    skipped=False,
                ),
            ]

        monkeypatch.setattr(data_cli, "download_dataset", fake_download)
        result = runner.invoke(app, ["data", "download", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "have retrievalqa/retrievalqa.jsonl" in result.stdout
        assert "got  retrievalqa/retrievalqa_gpt4.jsonl" in result.stdout

    def test_a_checksum_mismatch_during_download_exits_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An upstream file that changed is a decision to make, not a warning to skip."""
        from llmsearchbench.cli import data as data_cli
        from llmsearchbench.datasets import ChecksumMismatchError

        def fake_download(*args: object, **kwargs: object) -> list[object]:
            raise ChecksumMismatchError("expected sha256 abc, got sha256 def")

        monkeypatch.setattr(data_cli, "download_dataset", fake_download)
        result = runner.invoke(app, ["data", "download", "--root", str(tmp_path)])
        assert result.exit_code == 1
        assert "expected sha256" in result.stderr


class TestAttributionCommand:
    def test_regenerates_the_committed_files(self) -> None:
        result = runner.invoke(app, ["attribution"])
        assert result.exit_code == 0
        assert "SOURCES.md" in result.stdout


class TestTopLevel:
    def test_no_arguments_shows_help(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code != 0
        assert "Usage" in result.output

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "llmsearchbench" in result.stdout

    def test_an_unknown_command_is_rejected(self) -> None:
        result = runner.invoke(app, ["frobnicate"])
        assert result.exit_code != 0
