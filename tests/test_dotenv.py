"""Reading `.env`."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from llmsearchbench.dotenv import load_dotenv


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestLoadDotenv:
    def test_loads_simple_pairs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EXAMPLE_KEY", raising=False)
        load_dotenv(write(tmp_path / ".env", "EXAMPLE_KEY=abc123\n"))
        assert os.environ["EXAMPLE_KEY"] == "abc123"

    def test_skips_comments_and_blank_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("EXAMPLE_KEY", raising=False)
        loaded = load_dotenv(write(tmp_path / ".env", "# a comment\n\n  \nEXAMPLE_KEY=abc\n"))
        assert loaded == {"EXAMPLE_KEY": "abc"}

    def test_skips_empty_values(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unfilled placeholder must not shadow a real key from the shell."""
        monkeypatch.delenv("EXAMPLE_KEY", raising=False)
        assert load_dotenv(write(tmp_path / ".env", "EXAMPLE_KEY=\n")) == {}

    def test_strips_surrounding_quotes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("EXAMPLE_KEY", raising=False)
        load_dotenv(write(tmp_path / ".env", 'EXAMPLE_KEY="abc123"\n'))
        assert os.environ["EXAMPLE_KEY"] == "abc123"

    def test_the_environment_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit export should beat the file, not the other way round."""
        monkeypatch.setenv("EXAMPLE_KEY", "from-the-shell")
        load_dotenv(write(tmp_path / ".env", "EXAMPLE_KEY=from-the-file\n"))
        assert os.environ["EXAMPLE_KEY"] == "from-the-shell"

    def test_a_missing_file_is_not_an_error(self, tmp_path: Path) -> None:
        assert load_dotenv(tmp_path / "absent") == {}
