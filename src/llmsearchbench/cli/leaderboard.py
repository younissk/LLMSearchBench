"""`leaderboard`: compare every model that has been run."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from llmsearchbench.cli._shared import EXIT_BAD_INPUT
from llmsearchbench.paths import RESULTS, SITE, TASKS
from llmsearchbench.providers import UnknownModelError, get_model, provider_label
from llmsearchbench.scoring import runstats
from llmsearchbench.scoring.tooluse import score
from llmsearchbench.storage import load_attempts, read_jsonl
from llmsearchbench.types import LeaderboardRow, TaskLeaderboard
from llmsearchbench.types.tooluse import Bucket, ToolUseTask
from llmsearchbench.ui import console, fail, warn

app = typer.Typer()

TASK_SET = "tool-use-correctness"


def unslug(name: str) -> str:
    """Recover a model id from an attempts filename."""
    return name.replace("--", "/", 1).replace("-attempts", "")


@app.command()
def leaderboard(
    results_dir: Annotated[Path, typer.Option(help="Where attempts live.")] = (
        RESULTS / "local"
    ),
    task_set: Annotated[Path, typer.Option(help="The task set.")] = TASKS / f"{TASK_SET}.jsonl",
    sort_by: Annotated[
        str, typer.Option(help="decision | memory | search | no_tool | cost | adversarial")
    ] = "decision",
    complete_only: Annotated[
        bool, typer.Option(help="Hide models whose run did not finish.")
    ] = False,
) -> None:
    """Rank every model with a run on disk."""
    files = sorted(results_dir.glob("*-attempts.jsonl"))
    if not files:
        fail(f"no runs in {results_dir} - run `llmsearchbench run --model ...` first")
        raise typer.Exit(EXIT_BAD_INPUT)

    tasks = [ToolUseTask.model_validate(raw) for raw in read_jsonl(task_set)]
    by_id = {task.id: task for task in tasks}

    rows = []
    for path in files:
        model = unslug(path.stem)
        attempts = load_attempts(path)
        answered = {a.task_id for a in attempts}
        scored_tasks = [t for t in tasks if t.id in answered]
        if not scored_tasks:
            continue
        if complete_only and len(scored_tasks) < len(by_id):
            continue
        result = score(model, scored_tasks, attempts)
        stats = runstats.compute(model, scored_tasks, attempts)
        rows.append((model, result, stats, len(scored_tasks)))

    keys = {
        "decision": lambda r: -r[1].decision_accuracy,
        "adversarial": lambda r: -r[1].adversarial_accuracy,
        "cost": lambda r: r[2].cost.total_usd,
        "memory": lambda r: -(b.accuracy if (b := r[1].bucket_score(Bucket.MEMORY)) else 0),
        "search": lambda r: -(b.accuracy if (b := r[1].bucket_score(Bucket.SEARCH)) else 0),
        "no_tool": lambda r: -(b.accuracy if (b := r[1].bucket_score(Bucket.NO_TOOL)) else 0),
    }
    if sort_by not in keys:
        fail(f"unknown sort {sort_by!r}. Try: {', '.join(sorted(keys))}")
        raise typer.Exit(EXIT_BAD_INPUT)
    rows.sort(key=keys[sort_by])

    table = Table(
        title=f"Tool-use correctness — {len(rows)} model(s), sorted by {sort_by}",
        title_justify="left",
        header_style="heading",
    )
    table.add_column("Model")
    table.add_column("n", justify="right")
    table.add_column("Decision", justify="right")
    table.add_column("mem", justify="right")
    table.add_column("sea", justify="right")
    table.add_column("no_tool", justify="right")
    table.add_column("Adversarial", justify="right")
    table.add_column("Calls OK", justify="right")
    table.add_column("Cost", justify="right")

    def pct(value: float) -> str:
        return f"{value:.0%}"

    for model, result, stats, count in rows:
        partial = count < len(by_id)
        buckets = {b.bucket: b.accuracy for b in result.buckets}
        table.add_row(
            f"{model}{' [warn]*[/warn]' if partial else ''}",
            str(count),
            f"[heading]{pct(result.decision_accuracy)}[/heading]",
            pct(buckets.get(Bucket.MEMORY, 0)),
            pct(buckets.get(Bucket.SEARCH, 0)),
            pct(buckets.get(Bucket.NO_TOOL, 0)),
            pct(result.adversarial_accuracy),
            pct(result.well_formed_rate) if stats.search_calls_total else "-",
            f"${stats.cost.total_usd:.3f}" if stats.cost.priced else "free",
        )

    console.print(table)
    if any(count < len(by_id) for _, _, _, count in rows):
        warn("* marks an unfinished run; its numbers are on fewer items")

    console.print(
        "[muted]mem/sea/no_tool are the share of right search-or-not decisions "
        "in each bucket.[/muted]"
    )


@app.command("publish")
def publish(
    results_dir: Annotated[Path, typer.Option(help="Where attempts live.")] = (
        RESULTS / "local"
    ),
    task_set: Annotated[Path, typer.Option(help="The task set.")] = TASKS / f"{TASK_SET}.jsonl",
    site: Annotated[Path, typer.Option(help="The documentation site root.")] = SITE,
    include_partial: Annotated[
        bool, typer.Option(help="Publish runs that did not finish.")
    ] = False,
) -> None:
    """Write the leaderboard the documentation site renders.

    Regenerated from the recorded attempts, so a scoring change is a re-export
    rather than a re-run.
    """
    tasks = [ToolUseTask.model_validate(raw) for raw in read_jsonl(task_set)]
    rows: list[LeaderboardRow] = []
    skipped = 0

    for path in sorted(results_dir.glob("*-attempts.jsonl")):
        model_id = unslug(path.stem)
        attempts = load_attempts(path)
        answered = {a.task_id for a in attempts}
        scored_tasks = [t for t in tasks if t.id in answered]
        if not scored_tasks:
            continue

        complete = len(scored_tasks) == len(tasks)
        if not complete and not include_partial:
            skipped += 1
            continue

        result = score(model_id, scored_tasks, attempts)
        stats = runstats.compute(model_id, scored_tasks, attempts)
        try:
            spec = get_model(model_id)
            label, provider, is_free = spec.label, provider_label(model_id), spec.is_free
        except UnknownModelError:
            label, provider, is_free = model_id, "unknown", False

        buckets = {b.bucket: b.accuracy for b in result.buckets}

        rows.append(
            LeaderboardRow(
                model=model_id,
                label=label,
                provider=provider,
                items=len(scored_tasks),
                complete=complete,
                decision_accuracy=result.decision_accuracy,
                memory_accuracy=buckets.get(Bucket.MEMORY, 0.0),
                search_accuracy=buckets.get(Bucket.SEARCH, 0.0),
                no_tool_accuracy=buckets.get(Bucket.NO_TOOL, 0.0),
                adversarial_accuracy=result.adversarial_accuracy,
                well_formed_rate=result.well_formed_rate,
                over_search_memory=result.over_search_memory,
                over_search_no_tool=result.over_search_no_tool,
                under_search=result.under_search,
                cost_usd=stats.cost.total_usd,
                is_free=is_free,
                tokens_out_mean=stats.tokens.output_mean,
                reasoning_share=stats.tokens.reasoning_share,
                latency_mean_s=stats.time.mean_s,
            )
        )

    rows.sort(key=lambda row: -row.decision_accuracy)
    board = TaskLeaderboard(
        task=TASK_SET,
        title="Tool-use correctness",
        generated=date.today().isoformat(),
        task_items=len(tasks),
        rows=rows,
    )

    target = site / "src" / "data" / "results" / f"{TASK_SET}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        board.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8"
    )

    console.print(f"[ok]wrote[/ok] {target}  ({len(rows)} model(s))")
    if skipped:
        warn(f"{skipped} unfinished run(s) left out; pass --include-partial to publish them")
