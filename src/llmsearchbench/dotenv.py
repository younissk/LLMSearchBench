"""Reading `.env`.

Fifteen lines rather than a dependency. Values already in the environment win,
so `ANTHROPIC_API_KEY=... llmsearchbench run` beats whatever is in the file.
"""

from __future__ import annotations

import os
from pathlib import Path

from llmsearchbench.paths import REPO_ROOT

DEFAULT_PATH = REPO_ROOT / ".env"


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """Load `KEY=value` lines into the environment. Returns what it set."""
    target = path or DEFAULT_PATH
    if not target.exists():
        return {}

    loaded: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if not key or not value or key in os.environ:
            continue
        os.environ[key] = value
        loaded[key] = value
    return loaded
