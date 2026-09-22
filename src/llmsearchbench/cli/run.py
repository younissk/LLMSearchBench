"""`run` and `aggregate`: turning a task set into records."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from llmsearchbench.cli._shared import DEFAULT_OUT, EXIT_BAD_INPUT, EXIT_NOT_WIRED
from llmsearchbench.harness import NotConfiguredError, build_adapter
from llmsearchbench.paths import TASKS
from llmsearchbench.providers import UnknownModelError
from llmsearchbench.storage import load_records, load_tasks
from llmsearchbench.ui import console, fail, warn

app = typer.Typer()


@app.command()
def run(
    release: Annotated[str, typer.Option(help="Task set version, e.g. v0.1.0.")],
    model: Annotated[str, typer.Option(help="Model id; see `llmsearchbench models`.")],
    # Accepted now so the interface is stable; unused until the run loop is
    # wired to an adapter.
    out: Annotated[Path, typer.Option(help="Where to write run artefacts.")] = DEFAULT_OUT,  # noqa: ARG001
    tasks_dir: Annotated[Path, typer.Option(help="Where task sets live.")] = TASKS,
    tasks: Annotated[
        int | None, typer.Option(help="Run a stratified subset. Not a valid result.")
    ] = None,
) -> None:
    """Run one model against one task set."""
    tasks_path = tasks_dir / f"{release}.jsonl"
    if not tasks_path.exists():
        fail(f"no task set at {tasks_path}")
        raise typer.Exit(EXIT_BAD_INPUT)

    loaded = load_tasks(tasks_path)
    if tasks is not None:
        loaded = loaded[:tasks]
        warn(f"running {len(loaded)} tasks - a subset is not a valid result")

    # Fails until an adapter is wired up. That is deliberate: a benchmark that
    # quietly substitutes a different model produces numbers nobody can place.
    try:
        build_adapter(model)
    except UnknownModelError as error:
        fail(str(error.args[0]))
        raise typer.Exit(EXIT_BAD_INPUT) from None
    except NotConfiguredError as error:
        fail(str(error))
        raise typer.Exit(EXIT_NOT_WIRED) from None

    raise NotImplementedError(  # pragma: no cover - unreachable until an adapter exists
        "an adapter exists but the run loop is not wired to it yet; call harness.run_tasks()"
    )


@app.command()
def aggregate(
    # Both are accepted now and used once aggregation can reach gold sources
    # and prices; the interface should not change when that lands.
    release: Annotated[str, typer.Option(help="Release the records belong to.")],  # noqa: ARG001
    raw: Annotated[Path, typer.Option(help="Path to raw.jsonl.")],
    tasks_dir: Annotated[Path, typer.Option(help="Where task sets live.")] = TASKS,  # noqa: ARG001
) -> None:
    """Collapse raw.jsonl into summary.json."""
    records = load_records(raw)
    if not records:
        fail(f"no records in {raw}")
        raise typer.Exit(EXIT_BAD_INPUT)

    console.print(
        f"[muted]{raw}[/muted]: {len(records)} records, "
        f"{len({r.model for r in records})} models, "
        f"{len({r.task_id for r in records})} tasks"
    )
    fail(
        "aggregation needs the task set for gold sources and the model catalogue "
        "for prices; fill in prices in src/llmsearchbench/providers/registry.py first"
    )
    raise typer.Exit(EXIT_NOT_WIRED)
