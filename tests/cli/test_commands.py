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

runner = CliRunner()


@pytest.fixture(autouse=True)
def wide_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rich wraps to the terminal width; pin it so assertions do not depend on it."""
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("TERM", "dumb")


class TestRunCommand:
    @staticmethod
    def _task_set(directory: Path) -> Path:
        path = directory / "tasks.jsonl"
        path.write_text(
            json.dumps(
                {
                    "id": "t1",
                    "bucket": "no_tool",
                    "prompt": "hi",
                    "gold_answer": [],
                    "source": "test",
                    "subcategory": "test",
                    "adversarial": False,
                    "rationale": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_a_missing_task_set_exits_two(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["run", "--model", "claude-opus-5", "--task-set", str(tmp_path / "absent.jsonl")],
        )
        assert result.exit_code == 2
        assert "make tasks" in result.stderr

    def test_a_model_outside_the_catalogue_exits_two(self, tmp_path: Path) -> None:
        """A typo in a model id must not look like a missing key."""
        task_set = self._task_set(tmp_path)
        result = runner.invoke(
            app, ["run", "--model", "not-a-model", "--task-set", str(task_set)]
        )
        assert result.exit_code == 2
        assert "unknown model" in result.stderr

    def test_a_missing_key_says_which_variable_to_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        task_set = self._task_set(tmp_path)
        result = runner.invoke(
            app,
            [
                "run",
                "--model",
                "claude-opus-5",
                "--task-set",
                str(task_set),
                "--out",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 3
        assert "ANTHROPIC_API_KEY" in result.stderr


class TestScoreCommand:
    def test_missing_attempts_says_how_to_produce_them(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["score", "--model", "claude-opus-5", "--attempts", str(tmp_path / "none.jsonl")],
        )
        assert result.exit_code == 2
        assert "llmsearchbench run" in result.stderr


class TestModelsCommand:
    def test_lists_the_catalogue(self) -> None:
        result = runner.invoke(app, ["models"])
        assert result.exit_code == 0
        assert "claude-opus-5" in result.stdout

    def test_shows_when_each_model_was_priced(self) -> None:
        """A price with no date cannot be re-checked, and prices move."""
        result = runner.invoke(app, ["models"])
        assert "2026-" in result.stdout


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
            # The first file of each dataset reports as already present, the
            # rest as fetched, so the command has both cases to print. Some
            # datasets ship a single file, so this cannot index blindly.
            return [
                DownloadResult(
                    dataset=spec.key,
                    file=file.name,
                    path=root / file.name,
                    skipped=index == 0,
                )
                for index, file in enumerate(spec.files)
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
