"""The Rich consoles and the theme they share."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

__all__ = ["console", "err_console", "fail", "warn"]

THEME = Theme(
    {
        "ok": "green",
        "warn": "yellow",
        "error": "bold red",
        "muted": "dim",
        "metric": "cyan",
        "heading": "bold",
    }
)

#: Results and tables.
console = Console(theme=THEME)

#: Diagnostics. Kept separate so `llmsearchbench data list > file` stays clean.
err_console = Console(theme=THEME, stderr=True)


def fail(message: str) -> None:
    err_console.print(f"[error]error[/error] {message}")


def warn(message: str) -> None:
    err_console.print(f"[warn]warn[/warn] {message}")
