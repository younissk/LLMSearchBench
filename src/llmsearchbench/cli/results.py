"""`diff`, `validate`, and `publish`: working with a finished summary."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.table import Table

from llmsearchbench.cli._shared import EXIT_FAILED, EXIT_OK
from llmsearchbench.paths import SITE
from llmsearchbench.scoring import diff_summaries
from llmsearchbench.storage import load_summary, publish_to_site
from llmsearchbench.ui import console, err_console, fail, warn

app = typer.Typer()


@app.command(name="diff")
def diff_command(
    actual: Annotated[Path, typer.Argument(help="Your summary.json.")],
    reference: Annotated[Path, typer.Argument(help="The published summary.json.")],
) -> None:
    """Compare a reproduction against a published release."""
    report = diff_summaries(load_summary(actual), load_summary(reference))

    for model in report.missing_models:
        console.print(f"[error]missing[/error] {model}: in the reference, absent from yours")
    for model in report.extra_models:
        console.print(f"[warn]extra[/warn]   {model}: in yours, absent from the reference")

    if report.failures:
        table = Table(title="Out of tolerance", title_justify="left", header_style="heading")
        table.add_column("Model")
        table.add_column("Metric", style="metric")
        table.add_column("Yours", justify="right")
        table.add_column("Reference", justify="right")
        table.add_column("Delta", justify="right")
        table.add_column("Tolerance", justify="right")
        for delta in report.failures:
            table.add_row(
                delta.model,
                delta.metric,
                f"{delta.actual:.4g}",
                f"{delta.expected:.4g}",
                f"[error]{delta.delta:+.4g}[/error]",
                f"±{delta.tolerance:g}",
            )
        console.print(table)

    if report.matches:
        checked = len({delta.model for delta in report.deltas})
        console.print(f"[ok]match[/ok] {checked} models within tolerance")
        raise typer.Exit(EXIT_OK)
    raise typer.Exit(EXIT_FAILED)


@app.command()
def validate(
    summary_path: Annotated[Path, typer.Argument(metavar="SUMMARY", help="A summary.json.")],
) -> None:
    """Check a summary against the published schema."""
    try:
        summary = load_summary(summary_path)
    except ValidationError as error:
        fail(f"{summary_path} is not a valid summary:")
        for problem in error.errors():
            location = ".".join(str(part) for part in problem["loc"])
            err_console.print(f"  [error]{location}[/error]: {problem['msg']}")
        raise typer.Exit(EXIT_FAILED) from None
    except ValueError as error:
        fail(f"{summary_path}: {error}")
        raise typer.Exit(EXIT_FAILED) from None

    if summary.placeholder:
        warn("placeholder is true - the site will render a warning banner")

    console.print(
        f"[ok]valid[/ok] {summary.version}: {len(summary.rows)} models, "
        f"{summary.task_count} tasks"
    )


@app.command()
def publish(
    summary_path: Annotated[Path, typer.Argument(metavar="SUMMARY", help="A summary.json.")],
    site: Annotated[Path, typer.Option(help="The documentation site root.")] = SITE,
) -> None:
    """Copy a summary into the documentation site."""
    target = publish_to_site(load_summary(summary_path), site)
    console.print(f"[ok]wrote[/ok] {target}")
    console.print(
        "[muted]next: register it in docs/src/data/index.ts and bump LATEST, "
        "then cut a docs version for the release it supersedes[/muted]"
    )
