"""Run paired feature ablations and a combined pipeline evaluation."""

import argparse
import hashlib
import json
import math
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from uuid import uuid4

from huggingface_agents_langgraph.experiments import IMPROVEMENTS, normalize_experiment
from huggingface_agents_langgraph.local_evaluation import evaluate_validation_answers
from huggingface_agents_langgraph.pipeline_versions import V2_REFERENCE_ID
from huggingface_agents_langgraph.run_tracking import (
    read_record,
    run_pipeline,
    write_record,
)


def source_identity() -> dict:
    """Identify executable source and lockfile, including uncommitted changes."""
    root = Path(__file__).resolve().parents[2]
    files = (
        sorted((root / "src").rglob("*.py"))
        + sorted((root / "src").rglob("*.js"))
        + [root / "pyproject.toml", root / "uv.lock"]
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    try:
        revision = subprocess.run(
            ["git", "-c", f"safe.directory={root.as_posix()}", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        revision = None
    return {"git_revision": revision, "source_sha256": digest.hexdigest()}


def timing_summary(answers: list[dict]) -> dict:
    """Summarize observed timings without counting missing measurements as zero."""
    times = sorted(
        answer["duration_seconds"]
        for answer in answers
        if isinstance(answer.get("duration_seconds"), (int, float))
    )
    return {
        "count": len(times),
        "total_seconds": sum(times),
        "mean_seconds": mean(times) if times else None,
        "median_seconds": median(times) if times else None,
        "p95_seconds": times[max(0, math.ceil(len(times) * 0.95) - 1)]
        if times
        else None,
        "technical_errors": sum(bool(answer.get("error")) for answer in answers),
    }


def variant_config(
    reference: dict, variant: str, architecture: str | None = None
) -> dict:
    """Keep the model and capabilities fixed while changing one feature or all."""
    if variant not in {"baseline", "combined", *IMPROVEMENTS}:
        raise ValueError("Unknown evaluation variant")
    improvements = (
        list(IMPROVEMENTS)
        if variant == "combined"
        else ([] if variant == "baseline" else [variant])
    )
    name = (
        "V2 · Control repetido"
        if variant == "baseline"
        else ("V3 · Completo" if variant == "combined" else f"V3 · Solo {variant}")
    )
    overrides = {
        "name": name,
        "pipeline_version": "2" if variant == "baseline" else "3",
        "improvements": improvements,
    }
    if architecture is not None:
        overrides["architecture"] = architecture
    return normalize_experiment(reference | overrides)


def run_experiment(
    tasks: list[dict],
    config: dict,
    *,
    group_id: str,
    score: bool = True,
    record: dict | None = None,
    should_stop: Callable[[], bool] | None = None,
    on_progress: Callable[[dict], None] | None = None,
) -> dict:
    """Persist each completed task and evaluate labels only after agent execution.

    ``should_stop`` is checked before every task, never during one: a stopped
    experiment is stored as ``cancelled`` and can be resumed with ``record``.
    ``on_progress`` sees the record after each write.
    """
    tasks = [
        {key: task.get(key, "") for key in ("task_id", "question", "file_name")}
        for task in tasks
    ]
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise ValueError("Evaluation inputs contain duplicate task IDs")
    identity = source_identity()
    input_hash = hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest()
    if record is not None and (
        record.get("source_identity") != identity
        or record.get("task_set_sha256") != input_hash
        or record.get("config") != config
    ):
        raise ValueError(
            "Cannot resume an experiment with changed code, inputs or configuration"
        )
    record = record or {
        "id": str(uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "pipeline_version": config["pipeline_version"],
        "config": config,
        "evaluation_group_id": group_id,
        "reference_id": V2_REFERENCE_ID,
        "questions": tasks,
        "total_questions": len(tasks),
        "evaluation_scope": "full" if len(tasks) == 20 else "smoke",
        "task_set_sha256": input_hash,
        "source_identity": identity,
        "answers": [],
        "cache_policy": "Attachment/model download caches retained; no answer cache",
    }
    record["status"] = "running"
    write_record("experiments", record)
    if on_progress:
        on_progress(record)
    completed = {answer["task_id"] for answer in record["answers"]}
    for task in tasks:
        if task["task_id"] in completed:
            continue
        if should_stop and should_stop():
            record["status"] = "cancelled"
            write_record("experiments", record)
            if on_progress:
                on_progress(record)
            return record
        started = perf_counter()
        try:
            result = run_pipeline(task | {"experiment": config})
        except Exception as error:
            result = {
                "error": str(error),
                "submitted_answer": "",
                "route": "error",
                "run_id": getattr(error, "run_id", None),
                "llm_duration_seconds": getattr(error, "llm_duration_seconds", None),
            }
        answer = task | {
            key: result.get(key)
            for key in (
                "submitted_answer",
                "error",
                "route",
                "run_id",
                "llm_duration_seconds",
            )
        }
        answer["submitted_answer"] = answer["submitted_answer"] or ""
        answer["error"] = answer["error"] or ""
        answer["duration_seconds"] = round(perf_counter() - started, 3)
        if answer["run_id"]:
            trace = read_record("runs", answer["run_id"])
            answer["llm_calls"] = len(trace["calls"])
            answer["resources"] = trace.get("resources", {})
            answer["model_load_seconds"] = sum(
                call.get("model_load_seconds", 0) for call in trace["calls"]
            )
            answer["truncated_calls"] = sum(
                call.get("response", {}).get("choices", [{}])[0].get("finish_reason")
                == "length"
                for call in trace["calls"]
            )
            answer["completion_tokens"] = sum(
                call.get("response", {}).get("usage", {}).get("completion_tokens", 0)
                for call in trace["calls"]
            )
            answer["stage_seconds"] = {}
            for step in trace["steps"]:
                stage = step["node"]
                answer["stage_seconds"][stage] = (
                    answer["stage_seconds"].get(stage, 0) + step["duration_seconds"]
                )
        record["answers"].append(answer)
        record["metrics"] = timing_summary(record["answers"])
        record["average_duration_seconds"] = record["metrics"]["mean_seconds"]
        write_record("experiments", record)
        if on_progress:
            on_progress(record)
        print(
            f"{config['name']}: {len(record['answers'])}/{len(tasks)} "
            f"{answer['duration_seconds']:.1f}s "
            f"{'ERROR' if answer['error'] else 'answered'}",
            flush=True,
        )
    record["status"] = "completed"
    if score and len(tasks) == 20:
        try:
            evaluation = evaluate_validation_answers(record["answers"])
            correct = {
                item["task_id"]: item["correct"] for item in evaluation["results"]
            }
            for answer in record["answers"]:
                answer["locally_correct"] = correct[answer["task_id"]]
            record["local_score"] = {
                key: value for key, value in evaluation.items() if key != "results"
            }
        except (RuntimeError, ValueError) as error:
            record["evaluation_error"] = str(error)
    write_record("experiments", record)
    if on_progress:
        on_progress(record)
    return record


def main() -> None:
    """Run actual ablations on the frozen question set without official submission."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=["baseline", "combined", *IMPROVEMENTS],
        default=["baseline", *IMPROVEMENTS, "combined"],
    )
    parser.add_argument("--group-id", default=str(uuid4()))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--resume", help="UUID of a partially completed experiment")
    parser.add_argument(
        "--architecture",
        help="Stored architecture version (or builtin:gaia_v31) to compile and run",
    )
    args = parser.parse_args()
    reference = read_record("experiments", V2_REFERENCE_ID)
    if not 1 <= args.limit <= 20:
        parser.error("limit must be between 1 and 20")
    tasks = reference["answers"][: args.limit]
    if args.resume:
        record = read_record("experiments", args.resume)
        run_experiment(
            tasks,
            record["config"],
            group_id=record["evaluation_group_id"],
            record=record,
        )
        return
    for variant in args.variants:
        result = run_experiment(
            tasks,
            variant_config(reference["config"], variant, args.architecture),
            group_id=args.group_id,
        )
        print(
            json.dumps(
                {
                    "experiment_id": result["id"],
                    "variant": variant,
                    "metrics": result["metrics"],
                    "score": result.get("local_score"),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
