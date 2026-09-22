"""`models`: the catalogue of what is under test."""

from __future__ import annotations

import typer
from rich.table import Table

from llmsearchbench.providers import MODELS, get_provider
from llmsearchbench.ui import console

app = typer.Typer()


@app.command()
def models() -> None:
    """Show the model catalogue."""
    table = Table(title="Models under test", title_justify="left", header_style="heading")
    table.add_column("Model id")
    table.add_column("Provider")
    table.add_column("In $/Mtok", justify="right")
    table.add_column("Out $/Mtok", justify="right")
    table.add_column("Priced")

    for model_id, spec in sorted(MODELS.items()):
        provider = get_provider(spec.provider)
        table.add_row(
            model_id,
            provider.label,
            f"{spec.price_in_per_mtok:g}",
            f"{spec.price_out_per_mtok:g}",
            spec.priced_on or "[warn]UNPRICED[/warn]",
        )

    console.print(table)
