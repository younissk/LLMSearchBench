"""`data`: fetching and verifying the source datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
)
from rich.table import Table

from llmsearchbench.cli._shared import EXIT_BAD_INPUT, EXIT_FAILED
from llmsearchbench.datasets import (
    DATASETS,
    ChecksumMismatchError,
    DatasetSpec,
    UnknownDatasetError,
    download_dataset,
    get_dataset,
    verify_dataset,
)
from llmsearchbench.datasets.attribution import missing_license_files
from llmsearchbench.paths import DATA_RAW
from llmsearchbench.ui import console, fail, human_size, warn

app = typer.Typer(help="Fetch and verify source datasets.", no_args_is_help=True)

DatasetOption = Annotated[
    list[str] | None,
    typer.Option("--dataset", help="Restrict to one dataset key; repeatable."),
]
RootOption = Annotated[Path, typer.Option(help="Where raw data lives.")]


def _resolve(keys: list[str] | None) -> list[DatasetSpec]:
    try:
        return [get_dataset(key) for key in (keys or sorted(DATASETS))]
    except UnknownDatasetError as error:
        fail(str(error.args[0]))
        raise typer.Exit(EXIT_BAD_INPUT) from None


def _size_of(spec: DatasetSpec, filename: str) -> int:
    return next(file.size_bytes for file in spec.files if file.name == filename)


@app.command("list")
def data_list(dataset: DatasetOption = None) -> None:
    """Show the dataset registry."""
    specs = _resolve(dataset)

    table = Table(title="Source datasets", title_justify="left", header_style="heading")
    table.add_column("Dataset")
    table.add_column("Licence")
    table.add_column("Size", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("Pinned at")

    for spec in specs:
        table.add_row(
            spec.key,
            spec.license,
            human_size(spec.total_bytes),
            str(len(spec.files)),
            spec.pinned_commit[:10] or "-",
        )
    console.print(table)

    for spec in specs:
        console.print(f"\n[heading]{spec.key}[/heading] [muted]{spec.homepage}[/muted]")
        for file in spec.files:
            console.print(
                f"  {file.name:<26} {human_size(file.size_bytes):>9}  "
                f"[muted]{file.sha256[:16]}...[/muted]"
            )


@app.command("verify")
def data_verify(dataset: DatasetOption = None, root: RootOption = DATA_RAW) -> None:
    """Check raw data against the pinned checksums, without fetching anything."""
    failures = 0
    for spec in _resolve(dataset):
        for checked in verify_dataset(spec, root=root / spec.key):
            style = "ok" if checked.ok else "error"
            console.print(
                f"[{style}]{checked.status:<7}[/{style}] {checked.dataset}/{checked.file}"
            )
            failures += 0 if checked.ok else 1

    if failures:
        fail(f"{failures} file(s) missing or corrupt - run `make data`")
        raise typer.Exit(EXIT_FAILED)


@app.command("download")
def data_download(
    dataset: DatasetOption = None,
    root: RootOption = DATA_RAW,
    force: Annotated[
        bool, typer.Option(help="Re-download even when the checksum matches.")
    ] = False,
) -> None:
    """Download every source dataset, skipping what already verifies."""
    specs = _resolve(dataset)
    total = sum(spec.total_bytes for spec in specs)
    console.print(f"fetching {len(specs)} dataset(s), up to {human_size(total)}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        console=console,
        transient=True,
    ) as progress:
        for spec in specs:
            bar = progress.add_task(spec.key, total=spec.total_bytes)

            def advance(size: int, bar: TaskID = bar) -> None:
                progress.advance(bar, size)

            try:
                results = download_dataset(
                    spec, root=root / spec.key, force=force, on_bytes=advance
                )
            except ChecksumMismatchError as error:
                progress.stop()
                fail(str(error))
                raise typer.Exit(EXIT_FAILED) from None

            for fetched in results:
                if fetched.skipped:
                    progress.advance(bar, _size_of(spec, fetched.file))
                    console.print(f"[muted]have[/muted] {fetched.dataset}/{fetched.file}")
                else:
                    console.print(f"[ok]got [/ok] {fetched.dataset}/{fetched.file}")

    for license_file in missing_license_files():
        warn(
            f"attribution/licenses/{license_file} is missing - "
            "save the licence text we were given alongside the data"
        )
