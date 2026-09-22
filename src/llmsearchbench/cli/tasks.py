"""`tasks`: building and inspecting benchmark task sets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from llmsearchbench.cli._shared import EXIT_BAD_INPUT
from llmsearchbench.paths import TASKS
from llmsearchbench.storage import read_jsonl
from llmsearchbench.taskgen.tooluse import DEFAULT_SEED, build, save
from llmsearchbench.types.tooluse import Bucket, ToolUseTask
from llmsearchbench.ui import console, fail

app = typer.Typer(help="Build and inspect task sets.", no_args_is_help=True)

TASK_SET = "tool-use-correctness"


@app.command("build")
def build_command(
    out: Annotated[Path, typer.Option(help="Where to write the task set.")] = TASKS,
    seed: Annotated[int, typer.Option(help="Sampling seed; fixed for reproducibility.")] = (
        DEFAULT_SEED
    ),
    memory: Annotated[int, typer.Option(help="How many memory-bucket items.")] = 120,
    search: Annotated[int, typer.Option(help="How many search-bucket items.")] = 120,
) -> None:
    """Build the tool-use-correctness task set from the source datasets."""
    try:
        tasks, report = build(seed=seed, memory_size=memory, search_size=search)
    except FileNotFoundError as error:
        fail(str(error))
        raise typer.Exit(EXIT_BAD_INPUT) from None

    path = save(tasks, out / f"{TASK_SET}.jsonl")
    report_path = out / f"{TASK_SET}.report.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    console.print(f"[ok]wrote[/ok] {path}  ({len(tasks)} items)")
    console.print(f"[ok]wrote[/ok] {report_path}")
    _print_report(report.model_dump(mode="json"))


@app.command("stats")
def stats_command(
    path: Annotated[Path, typer.Option(help="The task set to describe.")] = (
        TASKS / f"{TASK_SET}.jsonl"
    ),
) -> None:
    """Describe a built task set."""
    if not path.exists():
        fail(f"no task set at {path} - run `make tasks`")
        raise typer.Exit(EXIT_BAD_INPUT)

    tasks = [ToolUseTask.model_validate(raw) for raw in read_jsonl(path)]

    table = Table(
        title=f"{path.name} - {len(tasks)} items", title_justify="left", header_style="heading"
    )
    table.add_column("Bucket")
    table.add_column("Items", justify="right")
    table.add_column("Expects search")
    table.add_column("Adversarial", justify="right")
    table.add_column("Subcategories")

    for bucket in Bucket:
        pool = [t for t in tasks if t.bucket is bucket]
        if not pool:
            continue
        subs = sorted({t.subcategory for t in pool})
        table.add_row(
            bucket.value,
            str(len(pool)),
            "yes" if bucket is Bucket.SEARCH else "no",
            str(sum(1 for t in pool if t.adversarial)),
            ", ".join(subs),
        )
    console.print(table)


def _print_report(report: dict[str, object]) -> None:
    dropped = report.get("dropped", {})
    if not isinstance(dropped, dict):
        return

    table = Table(
        title="Candidates dropped, by rule", title_justify="left", header_style="heading"
    )
    table.add_column("Bucket")
    table.add_column("Rule")
    table.add_column("Dropped", justify="right")
    for bucket, rules in dropped.items():
        if not isinstance(rules, dict):
            continue
        for rule, count in sorted(rules.items(), key=lambda kv: -int(kv[1])):
            table.add_row(bucket, rule, str(count))
    console.print(table)
