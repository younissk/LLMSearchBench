"""`run-discrimination` and `score-discrimination`: the second task's loop."""

from __future__ import annotations

from datetime import date
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
from llmsearchbench.cli.leaderboard import model_sizes
from llmsearchbench.harness import NotConfiguredError, build_adapter
from llmsearchbench.harness.discrimination import (
    DEFAULT_CONCURRENCY,
    DiscriminationAttempt,
    completed_task_ids,
    run_tasks,
)
from llmsearchbench.paths import RESULTS, SITE, TASKS
from llmsearchbench.providers import UnknownModelError, get_model, provider_label
from llmsearchbench.scoring.discrimination import Slice, score, score_item
from llmsearchbench.storage import read_jsonl
from llmsearchbench.types.discrimination import Category, DiscriminationTask
from llmsearchbench.types.leaderboard import (
    DiscriminationBoard,
    DiscriminationRow,
    DiscriminationSlice,
)
from llmsearchbench.ui import console, fail, warn

app = typer.Typer()

TASK_SET = "search-result-discrimination"


def slug(model_id: str) -> str:
    return model_id.replace("/", "--")


def scorable(task: DiscriminationTask) -> bool:
    """Can this item be marked right or wrong from the answer alone?

    The web category cannot: TREC judged which passages were relevant, not what
    the answer was, so there is nothing to compare an answer against. Its
    queries still earn their place as the no-answer items, where the right
    answer is that the results do not have one.
    """
    return bool(task.gold_answer) or not task.supporting_ids


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
    tasks = [task for task in map(DiscriminationTask.model_validate, rows) if scorable(task)]

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


def as_site_slice(slice_: Slice) -> DiscriminationSlice:
    """The scorer's slice in the shape the site reads."""
    return DiscriminationSlice(
        name=slice_.name,
        items=slice_.items,
        correct=slice_.correct,
        accuracy=slice_.accuracy,
    )


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
    show: Annotated[int, typer.Option(help="Print this many wrong answers.")] = 0,
) -> None:
    """Score a recorded run: was the answer right?"""
    attempts_path = results_dir / f"{slug(model)}-{TASK_SET}.jsonl"
    attempts = load_attempts(attempts_path)
    if not attempts:
        fail(f"no attempts at {attempts_path}")
        raise typer.Exit(EXIT_BAD_INPUT)

    by_id = {task.id: task for task in load_tasks(task_set, local_set, None, None)}
    scores = [
        score_item(by_id[a.task_id], a.reply)
        for a in attempts
        if a.task_id in by_id and not a.failed
    ]
    if not scores:
        fail("nothing scorable in this run")
        raise typer.Exit(EXIT_BAD_INPUT)

    result = score(model, scores, failed=sum(1 for a in attempts if a.failed))

    table = Table(
        title=f"{model} - {result.overall.correct}/{result.overall.items} correct",
        title_justify="left",
        header_style="heading",
    )
    table.add_column("Slice")
    table.add_column("Items", justify="right")
    table.add_column("Correct", justify="right")
    table.add_column("Accuracy", justify="right")

    for slice_, heading in [(result.overall, True)] + [
        (s, False) for s in result.by_category + result.by_tier
    ]:
        name = f"[heading]{slice_.name}[/heading]" if heading else slice_.name
        table.add_row(name, str(slice_.items), str(slice_.correct), f"{slice_.accuracy:.1%}")
    console.print(table)

    console.print(
        f"[muted]{result.fabricated} answered when the results had no answer; "
        f"{result.wrongly_refused} refused when they did.[/muted]"
    )
    if result.failed:
        warn(f"{result.failed} item(s) never came back and are not scored")

    for item in [s for s in scores if not s.correct][:show]:
        expected = "INSUFFICIENT" if item.unanswerable else "an answer"
        console.print(f"\n[warn]{item.task_id}[/warn] expected {expected}")
        console.print(f"  got: {item.answer[:200]}")


@app.command("publish-discrimination")
def publish_command(
    task_set: Annotated[Path, typer.Option(help="The shipped task set.")] = (
        TASKS / f"{TASK_SET}.jsonl"
    ),
    local_set: Annotated[Path, typer.Option(help="The locally built half.")] = (
        TASKS / "local" / f"{TASK_SET}-local.jsonl"
    ),
    results_dir: Annotated[Path, typer.Option(help="Where attempts live.")] = RESULTS / "local",
    site: Annotated[Path, typer.Option(help="The documentation site root.")] = SITE,
) -> None:
    """Write what the documentation site renders for this task."""
    tasks = load_tasks(task_set, local_set, None, None)
    by_id = {task.id: task for task in tasks}
    sizes = model_sizes()

    rows: list[DiscriminationRow] = []
    sample = 0
    for path in sorted(results_dir.glob(f"*-{TASK_SET}.jsonl")):
        model_id = path.stem.replace("--", "/", 1).replace(f"-{TASK_SET}", "")
        attempts = load_attempts(path)
        scores = [
            score_item(by_id[a.task_id], a.reply)
            for a in attempts
            if a.task_id in by_id and not a.failed
        ]
        if not scores:
            warn(f"{model_id}: nothing scorable; not published")
            continue

        result = score(model_id, scores, failed=sum(1 for a in attempts if a.failed))
        try:
            spec = get_model(model_id)
            label, provider, is_free = spec.label, provider_label(model_id), spec.is_free
        except UnknownModelError:
            label, provider, is_free = model_id, "unknown", False

        sample = max(sample, result.overall.items)
        rows.append(
            DiscriminationRow(
                model=model_id,
                label=label,
                provider=provider,
                is_free=is_free,
                params_b=sizes.get(model_id),
                scored=result.overall.items,
                failed=result.failed,
                fabricated=result.fabricated,
                wrongly_refused=result.wrongly_refused,
                overall=as_site_slice(result.overall),
                slices=[as_site_slice(s) for s in result.by_category + result.by_tier],
            )
        )

    rows.sort(key=lambda row: -row.overall.accuracy)
    board = DiscriminationBoard(
        task=TASK_SET,
        title="Search-result discrimination",
        generated=date.today().isoformat(),
        task_items=len(tasks),
        sample_items=sample,
        rows=rows,
    )

    target = site / "src" / "data" / "results" / f"{TASK_SET}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(board.model_dump_json(indent=2) + "\n", encoding="utf-8")
    console.print(f"[ok]wrote[/ok] {target}  ({len(rows)} model(s))")
    if sample < len(tasks):
        warn(f"a sample run: {sample} of {len(tasks)} scorable items")
