"""`run-discrimination` and `score-discrimination`: the second task's loop."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from llmsearchbench.cli._shared import EXIT_BAD_INPUT, EXIT_NOT_WIRED
from llmsearchbench.harness import NotConfiguredError, build_adapter
from llmsearchbench.harness.discrimination import (
    DEFAULT_CONCURRENCY,
    DiscriminationAttempt,
    completed_task_ids,
    run_tasks,
)
from llmsearchbench.paths import RESULTS, TASKS
from llmsearchbench.providers import UnknownModelError, get_model, provider_label
from llmsearchbench.scoring.discrimination import Slice, parse_output, score, score_item
from llmsearchbench.storage import read_jsonl
from llmsearchbench.types.discrimination import Category, DiscriminationTask
from llmsearchbench.ui import console, fail, warn

app = typer.Typer()

TASK_SET = "search-result-discrimination"


def slug(model_id: str) -> str:
    return model_id.replace("/", "--")


def load_tasks(
    task_set: Path, local_set: Path, limit: int | None, categories: list[str] | None
) -> list[DiscriminationTask]:
    """The shipped items plus the locally built ones, where they exist.

    A limit is spread across categories rather than sliced off the front: the
    file is grouped, so a flat slice would measure one category and call it the
    task.
    """
    rows = list(read_jsonl(task_set))
    if local_set.exists():
        rows += list(read_jsonl(local_set))
    tasks = [DiscriminationTask.model_validate(row) for row in rows]

    if categories:
        wanted = {Category(name) for name in categories}
        tasks = [task for task in tasks if task.category in wanted]
    if not limit:
        return tasks

    by_category: dict[Category, list[DiscriminationTask]] = {}
    for task in tasks:
        by_category.setdefault(task.category, []).append(task)

    picked: list[DiscriminationTask] = []
    order = list(by_category)
    while len(picked) < limit and any(by_category[key] for key in order):
        for key in order:
            if len(picked) >= limit:
                break
            if by_category[key]:
                picked.append(by_category[key].pop(0))
    return picked


def load_attempts(path: Path) -> list[DiscriminationAttempt]:
    if not path.exists():
        return []
    return [DiscriminationAttempt.model_validate(row) for row in read_jsonl(path)]


@app.command("run-discrimination")
def run_command(
    model: Annotated[str, typer.Option(help="Catalogued model id.")],
    task_set: Annotated[Path, typer.Option(help="The shipped task set.")] = (
        TASKS / f"{TASK_SET}.jsonl"
    ),
    local_set: Annotated[Path, typer.Option(help="The locally built half.")] = (
        TASKS / "local" / f"{TASK_SET}-local.jsonl"
    ),
    out: Annotated[Path, typer.Option(help="Where attempts are written.")] = RESULTS / "local",
    limit: Annotated[int, typer.Option(help="Run only this many items.")] = 0,
    category: Annotated[
        list[str] | None, typer.Option(help="Limit to a category; repeatable.")
    ] = None,
    concurrency: Annotated[int, typer.Option(help="Parallel requests.")] = DEFAULT_CONCURRENCY,
    yes: Annotated[bool, typer.Option("--yes", help="Skip the confirmation.")] = False,
) -> None:
    """Put the discrimination task to one model."""
    try:
        spec = get_model(model)
    except UnknownModelError as error:
        fail(str(error))
        raise typer.Exit(EXIT_BAD_INPUT) from None

    tasks = load_tasks(task_set, local_set, limit or None, category)
    if not tasks:
        fail(f"no items in {task_set} - run `make tasks-discrimination`")
        raise typer.Exit(EXIT_BAD_INPUT)

    out.mkdir(parents=True, exist_ok=True)
    attempts_path = out / f"{slug(model)}-{TASK_SET}.jsonl"
    done = completed_task_ids(attempts_path)
    todo = [task for task in tasks if task.id not in done]
    if done:
        console.print(f"[muted]resuming: {len(done)} item(s) already recorded[/muted]")
    if not todo:
        console.print("[ok]nothing to do[/ok]")
        return

    candidates = sum(task.candidate_count for task in todo)
    console.print(
        f"{len(todo)} item(s) · {model} ({provider_label(model)}) · "
        f"{candidates} candidate(s) · {concurrency} at a time"
        + (" · free endpoint" if spec.is_free else "")
    )
    if not yes and not typer.confirm("Run?", default=True):
        raise typer.Exit(0)

    try:
        adapter = build_adapter(model)
    except NotConfiguredError as error:
        fail(str(error))
        raise typer.Exit(EXIT_NOT_WIRED) from None

    with Progress(
        TextColumn("[heading]{task.description}[/heading]"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        bar = progress.add_task(model, total=len(todo))

        def tick(
            _done: int,
            _total: int,
            _task: DiscriminationTask,
            attempt: DiscriminationAttempt,
        ) -> None:
            progress.update(bar, advance=1)
            if attempt.failed:
                progress.console.print(f"[warn]{attempt.task_id}: {attempt.error}[/warn]")

        run_tasks(
            todo,
            model,
            adapter,
            out_path=attempts_path,
            on_item=tick,
            concurrency=concurrency,
        )

    console.print(f"[ok]wrote[/ok] {attempts_path}")
    console.print(f"next: llmsearchbench score-discrimination --model {model}")


@app.command("score-discrimination")
def score_command(
    model: Annotated[str, typer.Option(help="Catalogued model id.")],
    task_set: Annotated[Path, typer.Option(help="The shipped task set.")] = (
        TASKS / f"{TASK_SET}.jsonl"
    ),
    local_set: Annotated[Path, typer.Option(help="The locally built half.")] = (
        TASKS / "local" / f"{TASK_SET}-local.jsonl"
    ),
    results_dir: Annotated[Path, typer.Option(help="Where attempts live.")] = RESULTS / "local",
) -> None:
    """Score a recorded run. No judge: every number here is arithmetic."""
    attempts_path = results_dir / f"{slug(model)}-{TASK_SET}.jsonl"
    attempts = load_attempts(attempts_path)
    if not attempts:
        fail(f"no attempts at {attempts_path}")
        raise typer.Exit(EXIT_BAD_INPUT)

    by_id = {task.id: task for task in load_tasks(task_set, local_set, None, None)}
    scores = []
    for attempt in attempts:
        task = by_id.get(attempt.task_id)
        if task is None or attempt.failed:
            continue
        output, problems = parse_output(attempt.reply, [c.id for c in task.candidates])
        scores.append(score_item(task, output, problems))

    if not scores:
        fail("every attempt failed; nothing to score")
        raise typer.Exit(EXIT_BAD_INPUT)

    result = score(model, scores)
    failed = sum(1 for a in attempts if a.failed)

    table = Table(
        title=f"{model} - {result.overall.items} scored item(s)",
        title_justify="left",
        header_style="heading",
    )
    table.add_column("Slice")
    table.add_column("Items", justify="right")
    table.add_column("Rankable", justify="right")
    table.add_column("nDCG@10", justify="right")
    table.add_column("Precision", justify="right")
    table.add_column("Recall", justify="right")
    table.add_column("Noise picked", justify="right")
    table.add_column("Abstention", justify="right")
    table.add_column("Answer", justify="right")

    def cell(value: float | None) -> str:
        """A dash where the measure does not apply, never a zero."""
        return "-" if value is None else f"{value:.3f}"

    def row(slice_: Slice, *, heading: bool = False) -> None:
        table.add_row(
            f"[heading]{slice_.name}[/heading]" if heading else slice_.name,
            str(slice_.items),
            str(slice_.rankable),
            cell(slice_.ndcg),
            cell(slice_.precision),
            cell(slice_.recall),
            cell(slice_.noise_picked),
            cell(slice_.abstention_accuracy),
            cell(slice_.answer_accuracy),
        )

    row(result.overall, heading=True)
    for slice_ in result.by_category + result.by_tier:
        row(slice_)
    console.print(table)

    if result.unparsed:
        warn(f"{result.unparsed} reply/replies could not be parsed; they are not scored")
    if failed:
        warn(f"{failed} item(s) failed outright and were left out")
    if result.parse_problems:
        detail = ", ".join(
            f"{kind} {count}" for kind, count in sorted(result.parse_problems.items())
        )
        console.print(f"[muted]parse repairs: {detail}[/muted]")
    console.print(
        "[muted]a dash means the measure does not apply: a no_answer item has "
        "nothing to rank and nothing to recall, so it counts only toward "
        "abstention and noise picked.[/muted]"
    )
    console.print("[muted]groundedness is not scored here: no judge has been run.[/muted]")
