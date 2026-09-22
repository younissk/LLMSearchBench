"""Line-oriented JSON, the format every run artefact is written in.

JSONL is chosen so a run can append as it goes: an interrupted run keeps
everything it already paid for.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Stream a JSONL file, skipping blank lines."""
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed: dict[str, Any] = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{number}: {error.msg}") from error
            yield parsed


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def append_line(path: Path, text: str) -> None:
    """Append one line, creating the directory if it is not there yet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        handle.write("\n")
