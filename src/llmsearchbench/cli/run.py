"""`run` and `score`: putting a model through the task set and reading the result."""

from __future__ import annotations

import json
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
from llmsearchbench.harness import (
    BackendNotConfiguredError,
    HarnessConfig,
    NotConfiguredError,
    build_adapter,
    build_backend,
)
from llmsearchbench.harness.search import LIVE_BACKENDS, SearchError
from llmsearchbench.harness.tooluse import completed_task_ids, run_tasks
from llmsearchbench.paths import RESULTS, TASKS
from llmsearchbench.providers import UnknownModelError, get_model, provider_label
from llmsearchbench.scoring import runstats
from llmsearchbench.scoring.tooluse import score
from llmsearchbench.storage import read_jsonl
from llmsearchbench.types.tooluse import Bucket, ToolUseAttempt, ToolUseTask
from llmsearchbench.ui import console, fail, warn

app = typer.Typer()

TASK_SET = "tool-use-correctness"
DEFAULT_BACKEND = "tavily"


def slug(model_id: str) -> str:
    """A filename-safe model id. Provider-prefixed ids contain a slash."""
    return model_id.replace("/", "--")


def _load_tasks(path: Path, limit: int | None, buckets: list[str] | None) -> list[ToolUseTask]:
    tasks = [ToolUseTask.model_validate(raw) for raw in read_jsonl(path)]
    if buckets:
        wanted = {Bucket(name) for name in buckets}
        tasks = [task for task in tasks if task.bucket in wanted]
    if not limit:
        return tasks

    # Take the limit evenly across buckets. A flat slice would return only the
    # first bucket, which makes a smoke run measure nothing about the others.
    by_bucket: dict[Bucket, list[ToolUseTask]] = {}
    for task in tasks:
        by_bucket.setdefault(task.bucket, []).append(task)

    picked: list[ToolUseTask] = []
    order = list(by_bucket)
    while len(picked) < limit and any(by_bucket[bucket] for bucket in order):
        for bucket in order:
            if len(picked) >= limit:
                break
            if by_bucket[bucket]:
                picked.append(by_bucket[bucket].pop(0))
    return sorted(picked, key=lambda task: task.id)


def _estimate(tasks: list[ToolUseTask], model_id: str) -> float:
    """Rough dollar estimate, so nobody starts a run blind."""
    spec = get_model(model_id)
    # Measured shape of a turn: ~700 input tokens, ~250 output, and roughly a
    # third of items take a second turn after a search.
    per_item_in, per_item_out = 900, 300
    return (
        len(tasks) * per_item_in / 1_000_000 * spec.price_in_per_mtok
        + len(tasks) * per_item_out / 1_000_000 * spec.price_out_per_mtok
    )


@app.command()
def run(
    model: Annotated[str, typer.Option(help="Model id; see `llmsearchbench models`.")],
    task_set: Annotated[Path, typer.Option(help="The task set.")] = TASKS / f"{TASK_SET}.jsonl",
    out: Annotated[Path, typer.Option(help="Where to write attempts.")] = RESULTS / "local",
    backend: Annotated[str, typer.Option(help="Search backend.")] = DEFAULT_BACKEND,
    effort: Annotated[str, typer.Option(help="low | medium | high | xhigh | max.")] = "high",
    limit: Annotated[int | None, typer.Option(help="Run only the first N items.")] = None,
    bucket: Annotated[
        list[str] | None, typer.Option(help="Restrict to a bucket; repeatable.")
    ] = None,
    resume: Annotated[bool, typer.Option(help="Skip items already recorded.")] = True,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the cost prompt.")] = False,
) -> None:
    """Run a model against the tool-use-correctness task set."""
    if not task_set.exists():
        fail(f"no task set at {task_set} - run `make tasks`")
        raise typer.Exit(EXIT_BAD_INPUT)

    try:
        tasks = _load_tasks(task_set, limit, bucket)
    except ValueError as error:
        fail(str(error))
        raise typer.Exit(EXIT_BAD_INPUT) from None

    attempts_path = out / f"{slug(model)}-attempts.jsonl"
    done = completed_task_ids(attempts_path) if resume else set()
    if done:
        tasks = [task for task in tasks if task.id not in done]
        console.print(f"[muted]resuming: {len(done)} item(s) already recorded[/muted]")

    if not tasks:
        console.print("[ok]nothing to do[/ok] - every item already has an attempt")
        return

    try:
        adapter = build_adapter(model, effort=effort)
        search = build_backend(backend)
    except UnknownModelError as error:
        fail(str(error.args[0]))
        raise typer.Exit(EXIT_BAD_INPUT) from None
    except (NotConfiguredError, BackendNotConfiguredError) as error:
        fail(str(error))
        raise typer.Exit(EXIT_NOT_WIRED) from None

    if backend not in LIVE_BACKENDS:
        warn(
            f"backend {backend!r} returns no results - decisions and call quality "
            "are still measured, but answers cannot be right. Not publishable."
        )

    estimate = _estimate(tasks, model)
    console.print(
        f"{len(tasks)} item(s) · {model} ({provider_label(model)}) · {backend} · "
        f"effort {effort} · roughly [metric]${estimate:.2f}[/metric]"
    )
    if not yes and not typer.confirm("Run it?", default=True):
        raise typer.Exit(0)

    searched = 0
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        bar = progress.add_task(model, total=len(tasks))

        def on_item(
            _index: int, _total: int, _task: ToolUseTask, attempt: ToolUseAttempt
        ) -> None:
            nonlocal searched
            searched += 1 if attempt.searched else 0
            progress.update(bar, advance=1, description=f"{model}  {searched} searched")

        try:
            run_tasks(
                tasks,
                model,
                adapter,
                search,
                HarnessConfig(),
                out_path=attempts_path,
                on_item=on_item,
            )
        except SearchError as error:
            progress.stop()
            fail(f"search backend failed: {error}")
            warn(f"partial results are in {attempts_path}; rerun to resume")
            raise typer.Exit(EXIT_NOT_WIRED) from None

    console.print(f"[ok]wrote[/ok] {attempts_path}")
    console.print(f"[muted]next: llmsearchbench score --model {model}[/muted]")


@app.command(name="score")
def score_command(
    model: Annotated[str, typer.Option(help="Model whose attempts to score.")],
    task_set: Annotated[Path, typer.Option(help="The task set.")] = TASKS / f"{TASK_SET}.jsonl",
    attempts: Annotated[Path | None, typer.Option(help="Attempts file.")] = None,
    out: Annotated[Path | None, typer.Option(help="Where to write the score.")] = None,
) -> None:
    """Score a finished run."""
    attempts_path = attempts or RESULTS / "local" / f"{slug(model)}-attempts.jsonl"
    if not attempts_path.exists():
        fail(f"no attempts at {attempts_path} - run `llmsearchbench run --model {model}`")
        raise typer.Exit(EXIT_BAD_INPUT)

    tasks = [ToolUseTask.model_validate(raw) for raw in read_jsonl(task_set)]
    recorded = [ToolUseAttempt.model_validate(raw) for raw in read_jsonl(attempts_path)]
    answered = {attempt.task_id for attempt in recorded}
    scored_tasks = [task for task in tasks if task.id in answered]

    if len(scored_tasks) < len(tasks):
        warn(f"scoring {len(scored_tasks)} of {len(tasks)} items - the run is incomplete")

    try:
        result = score(model, scored_tasks, recorded)
    except ValueError as error:
        fail(str(error))
        raise typer.Exit(EXIT_BAD_INPUT) from None

    stats = runstats.compute(model, scored_tasks, recorded)
    _render(result)
    _render_stats(stats)

    target = out or RESULTS / "local" / f"{slug(model)}-score.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "score": result.model_dump(mode="json"),
                "run": stats.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    console.print(f"\n[ok]wrote[/ok] {target}")


def _render(result: object) -> None:
    from llmsearchbench.scoring.tooluse import ToolUseScore

    assert isinstance(result, ToolUseScore)

    decision = Table(title="1. Decision", title_justify="left", header_style="heading")
    decision.add_column("Bucket")
    decision.add_column("Items", justify="right")
    decision.add_column("Right call", justify="right")
    for bucket in result.buckets:
        if bucket.items:
            decision.add_row(bucket.bucket.value, str(bucket.items), f"{bucket.accuracy:.1%}")
    decision.add_row(
        "[heading]overall[/heading]",
        str(result.items),
        f"[heading]{result.decision_accuracy:.1%}[/heading]",
    )
    console.print(decision)

    rates = Table(title="Failure modes", title_justify="left", header_style="heading")
    rates.add_column("Metric")
    rates.add_column("Rate", justify="right")
    rates.add_column("Means")
    rates.add_row(
        "over-search (memory)",
        f"{result.over_search_memory:.1%}",
        "knew the answer, searched anyway",
    )
    rates.add_row(
        "over-search (no_tool)",
        f"{result.over_search_no_tool:.1%}",
        "searched when there was no fact",
    )
    rates.add_row(
        "under-search", f"{result.under_search:.1%}", "answered something it could not know"
    )
    rates.add_row(
        "adversarial accuracy",
        f"{result.adversarial_accuracy:.1%}",
        "right call on the trick questions",
    )
    console.print(rates)

    calls = Table(title="2. Call quality", title_justify="left", header_style="heading")
    calls.add_column("Measure")
    calls.add_column("Value", justify="right")
    calls.add_row("items that called", str(result.items_with_calls))
    calls.add_row("calls total", str(result.calls_total))
    calls.add_row("well formed", f"{result.well_formed_rate:.1%}")
    for problem, count in result.problem_counts.items():
        calls.add_row(f"[warn]{problem}[/warn]", str(count))
    console.print(calls)

    answers = Table(title="3. Answer", title_justify="left", header_style="heading")
    answers.add_column("Bucket")
    answers.add_column("Correct", justify="right")
    answers.add_row("memory", f"{result.answer_accuracy_memory:.1%}")
    answers.add_row("search", f"{result.answer_accuracy_search:.1%}")
    console.print(answers)


def _render_stats(stats: runstats.RunStats) -> None:
    """Cost, tokens, and time. What the run spent, not how good it was."""
    money = Table(title="4. Cost", title_justify="left", header_style="heading")
    money.add_column("Measure")
    money.add_column("Value", justify="right")
    if stats.cost.priced:
        money.add_row("total", f"${stats.cost.total_usd:.4f}")
        money.add_row("per item", f"${stats.cost.mean_usd:.5f}")
        money.add_row("per 1,000 items", f"${stats.cost.per_1k_items_usd:.2f}")
        money.add_row(
            "input / output", f"${stats.cost.input_usd:.4f} / ${stats.cost.output_usd:.4f}"
        )
        money.add_row(
            "[warn]wasted on needless searches[/warn]",
            f"${stats.cost.wasted_usd:.4f} ({stats.cost.wasted_share:.1%})",
        )
        money.add_row("per right decision", f"${stats.cost.usd_per_correct_decision:.5f}")
    else:
        money.add_row("[warn]unpriced[/warn]", "add prices in providers/registry.py")
    console.print(money)

    tokens = Table(title="5. Tokens", title_justify="left", header_style="heading")
    tokens.add_column("Measure")
    tokens.add_column("Total", justify="right")
    tokens.add_column("Mean", justify="right")
    tokens.add_row("input", f"{stats.tokens.input_total:,}", f"{stats.tokens.input_mean:,.0f}")
    tokens.add_row(
        "output", f"{stats.tokens.output_total:,}", f"{stats.tokens.output_mean:,.0f}"
    )
    if stats.tokens.reasoning_total:
        tokens.add_row(
            "of which thinking",
            f"{stats.tokens.reasoning_total:,} ({stats.tokens.reasoning_share:.0%})",
            f"{stats.tokens.reasoning_mean:,.0f}",
        )
    if stats.tokens.cached_total:
        tokens.add_row("cached input", f"{stats.tokens.cached_total:,}", "")
    tokens.add_row(
        "output median / p95 / max",
        "",
        f"{stats.tokens.output_median:,.0f} / {stats.tokens.output_p95:,.0f} / "
        f"{stats.tokens.output_max:,}",
    )
    console.print(tokens)

    clock = Table(title="6. Time", title_justify="left", header_style="heading")
    clock.add_column("Measure")
    clock.add_column("Value", justify="right")
    clock.add_row("total", f"{stats.time.total_s:,.1f}s")
    clock.add_row("mean / median", f"{stats.time.mean_s:.1f}s / {stats.time.median_s:.1f}s")
    clock.add_row("p95 / max", f"{stats.time.p95_s:.1f}s / {stats.time.max_s:.1f}s")
    clock.add_row(
        "searched vs direct",
        f"{stats.time.mean_s_searched:.1f}s vs {stats.time.mean_s_direct:.1f}s "
        f"(+{stats.time.search_overhead_s:.1f}s)",
    )
    clock.add_row("throughput", f"{stats.items_per_minute:.1f} items/min")
    console.print(clock)

    effort = Table(title="7. Effort per bucket", title_justify="left", header_style="heading")
    effort.add_column("Bucket")
    effort.add_column("Items", justify="right")
    effort.add_column("Out tokens", justify="right")
    effort.add_column("Thinking", justify="right")
    effort.add_column("Latency", justify="right")
    effort.add_column("Calls", justify="right")
    effort.add_column("Cost", justify="right")
    for bucket in stats.buckets:
        effort.add_row(
            bucket.bucket.value,
            str(bucket.items),
            f"{bucket.tokens_out_mean:,.0f}",
            f"{bucket.reasoning_mean:,.0f}" if stats.tokens.reasoning_total else "-",
            f"{bucket.latency_mean_s:.1f}s",
            f"{bucket.search_calls_mean:.2f}",
            f"${bucket.cost_usd:.4f}" if stats.cost.priced else "-",
        )
    console.print(effort)

    console.print(
        f"[muted]{stats.turns_total} API turns ({stats.turns_mean:.2f}/item) · "
        f"{stats.search_calls_total} search calls · "
        f"{stats.items_searching_repeatedly} item(s) searched more than once · "
        f"answers averaged {stats.answer_chars_mean:.0f} characters"
        + (f" · {stats.failed_items} failed" if stats.failed_items else "")
        + "[/muted]"
    )
