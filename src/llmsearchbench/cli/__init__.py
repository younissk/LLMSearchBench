"""The command line, one module per command group.

    llmsearchbench run         --release v0.1.0 --model <id>
    llmsearchbench aggregate   --release v0.1.0 --raw results/local/raw.jsonl
    llmsearchbench diff        results/local/summary.json results/v0.1.0/summary.json
    llmsearchbench validate    results/v0.1.0/summary.json
    llmsearchbench publish     results/v0.1.0/summary.json
    llmsearchbench models
    llmsearchbench data        list | download | verify
    llmsearchbench attribution

Typer and Rich live here and in `llmsearchbench.ui`; nothing below them knows
a terminal exists.
"""

from __future__ import annotations

from typing import Annotated

import typer

from llmsearchbench import __version__
from llmsearchbench.cli import attribution, catalogue, data, results, run, tasks
from llmsearchbench.cli._shared import (
    EXIT_BAD_INPUT,
    EXIT_FAILED,
    EXIT_NOT_WIRED,
    EXIT_OK,
)
from llmsearchbench.dotenv import load_dotenv
from llmsearchbench.ui import console

__all__ = ["EXIT_BAD_INPUT", "EXIT_FAILED", "EXIT_NOT_WIRED", "EXIT_OK", "app", "main"]

app = typer.Typer(
    name="llmsearchbench",
    help="A small, reproducible benchmark for how models use search.",
    no_args_is_help=True,
    add_completion=False,
)

for group in (run.app, results.app, catalogue.app, attribution.app):
    app.registered_commands.extend(group.registered_commands)

app.add_typer(data.app, name="data")
app.add_typer(tasks.app, name="tasks")


# Keys live in .env; load them before any command reads the environment.
load_dotenv()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"llmsearchbench {__version__}")
        raise typer.Exit(EXIT_OK)


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    """A small, reproducible benchmark for how models use search."""


def main() -> None:  # pragma: no cover - the installed console script
    app()
