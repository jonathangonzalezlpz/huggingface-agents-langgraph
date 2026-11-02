"""Run an experiment: every task through the pipeline, persisted as it completes."""

import hashlib
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from huggingface_agents_langgraph.adapters.records import read_record, write_record
from huggingface_agents_langgraph.application.pipeline_run import run_pipeline
from huggingface_agents_langgraph.domain.experiment_metrics import timing_summary
from huggingface_agents_langgraph.domain.experiments import (
    IMPROVEMENTS,
    normalize_experiment,
)
from huggingface_agents_langgraph.domain.local_evaluation import (
    evaluate_validation_answers,
)
from huggingface_agents_langgraph.domain.pipeline_versions import V2_REFERENCE_ID

FULL_SET_SIZE = 20
ANSWER_FIELDS = (
    "submitted_answer",
    "error",
    "route",
    "run_id",
    "llm_duration_seconds",
)


def source_identity() -> dict:
    """Identify executable source and lockfile, including uncommitted changes.

    Only Python sources count: the built interface is output, and rebuilding it must not
    make otherwise identical experiments look like they ran different code.
    """
    root = Path(__file__).resolve().parents[3]
    files = sorted((root / "src").rglob("*.py")) + [
        root / "pyproject.toml",
        root / "uv.lock",
    ]
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


def _task_hash(tasks: list[dict]) -> str:
    return hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest()


def _new_record(tasks: list[dict], config: dict, group_id: str, identity: dict) -> dict:
    return {
        "id": str(uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "pipeline_version": config["pipeline_version"],
        "config": config,
        "evaluation_group_id": group_id,
        "reference_id": V2_REFERENCE_ID,
        "questions": tasks,
        "total_questions": len(tasks),
        "evaluation_scope": "full" if len(tasks) == FULL_SET_SIZE else "smoke",
        "task_set_sha256": _task_hash(tasks),
        "source_identity": identity,
        "answers": [],
        "cache_policy": "Attachment/model download caches retained; no answer cache",
    }


def _check_resumable(record: dict, tasks: list[dict], config: dict, identity: dict):
    if (
        record.get("source_identity") != identity
        or record.get("task_set_sha256") != _task_hash(tasks)
        or record.get("config") != config
    ):
        raise ValueError(
            "Cannot resume an experiment with changed code, inputs or configuration"
        )


def _execute(task: dict, config: dict) -> dict:
    """The pipeline result, or an error result when the run raised."""
    try:
        return run_pipeline(task | {"experiment": config})
    except Exception as error:
        return {
            "error": str(error),
            "submitted_answer": "",
            "route": "error",
            "run_id": getattr(error, "run_id", None),
            "llm_duration_seconds": getattr(error, "llm_duration_seconds", None),
        }


def _trace_figures(run_id: str) -> dict:
    """Calls, tokens, load time and per-stage seconds read from a stored run."""
    trace = read_record("runs", run_id)
    calls = trace["calls"]
    stage_seconds: dict[str, float] = {}
    for step in trace["steps"]:
        stage = step["node"]
        stage_seconds[stage] = stage_seconds.get(stage, 0) + step["duration_seconds"]
    return {
        "llm_calls": len(calls),
        "resources": trace.get("resources", {}),
        "model_load_seconds": sum(call.get("model_load_seconds", 0) for call in calls),
        "truncated_calls": sum(
            call.get("response", {}).get("choices", [{}])[0].get("finish_reason")
            == "length"
            for call in calls
        ),
        "completion_tokens": sum(
            call.get("response", {}).get("usage", {}).get("completion_tokens", 0)
            for call in calls
        ),
        "stage_seconds": stage_seconds,
    }


def _answer_for(task: dict, config: dict) -> dict:
    """Run one task and describe its outcome as a stored answer."""
    started = perf_counter()
    result = _execute(task, config)
    answer = task | {key: result.get(key) for key in ANSWER_FIELDS}
    answer["submitted_answer"] = answer["submitted_answer"] or ""
    answer["error"] = answer["error"] or ""
    answer["duration_seconds"] = round(perf_counter() - started, 3)
    if answer["run_id"]:
        answer |= _trace_figures(answer["run_id"])
    return answer


def _score_locally(record: dict) -> None:
    """Add the local score; a failure is kept in the record, not raised."""
    try:
        evaluation = evaluate_validation_answers(record["answers"])
    except (RuntimeError, ValueError) as error:
        record["evaluation_error"] = str(error)
        return
    correct = {item["task_id"]: item["correct"] for item in evaluation["results"]}
    for answer in record["answers"]:
        answer["locally_correct"] = correct[answer["task_id"]]
    record["local_score"] = {
        key: value for key, value in evaluation.items() if key != "results"
    }


def _clean_tasks(tasks: list[dict]) -> list[dict]:
    cleaned = [
        {key: task.get(key, "") for key in ("task_id", "question", "file_name")}
        for task in tasks
    ]
    if len({task["task_id"] for task in cleaned}) != len(cleaned):
        raise ValueError("Evaluation inputs contain duplicate task IDs")
    return cleaned


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
    tasks = _clean_tasks(tasks)
    identity = source_identity()
    if record is not None:
        _check_resumable(record, tasks, config, identity)
    record = record or _new_record(tasks, config, group_id, identity)

    def save(status: str | None = None) -> None:
        if status:
            record["status"] = status
        write_record("experiments", record)
        if on_progress:
            on_progress(record)

    save("running")
    completed = {answer["task_id"] for answer in record["answers"]}
    for task in tasks:
        if task["task_id"] in completed:
            continue
        if should_stop and should_stop():
            save("cancelled")
            return record
        answer = _answer_for(task, config)
        record["answers"].append(answer)
        record["metrics"] = timing_summary(record["answers"])
        record["average_duration_seconds"] = record["metrics"]["mean_seconds"]
        save()
        print(
            f"{config['name']}: {len(record['answers'])}/{len(tasks)} "
            f"{answer['duration_seconds']:.1f}s "
            f"{'ERROR' if answer['error'] else 'answered'}",
            flush=True,
        )
    record["status"] = "completed"
    if score and len(tasks) == FULL_SET_SIZE:
        _score_locally(record)
    save()
    return record
