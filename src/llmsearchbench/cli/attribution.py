"""`attribution`: regenerating the licence and citation files."""

from __future__ import annotations

import typer

from llmsearchbench.datasets.attribution import write_all
from llmsearchbench.ui import console

app = typer.Typer()


@app.command()
def attribution() -> None:
    """Regenerate the licence, citation, and data-source files."""
    for path in write_all():
        console.print(f"[ok]wrote[/ok] {path}")
