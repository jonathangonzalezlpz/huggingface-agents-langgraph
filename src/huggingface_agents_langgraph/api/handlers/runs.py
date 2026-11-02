"""Run one task through the pipeline, and read the record of a past run."""

import json
from time import perf_counter

from huggingface_agents_langgraph.api.http import (
    JsonResponse,
    Request,
    Response,
    failure,
    ok,
)
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.experiments import normalize_experiment
from huggingface_agents_langgraph.pipeline_run import run_pipeline
from huggingface_agents_langgraph.records import read_record


def validate_task(payload: object) -> dict:
    """The task to run, with the experiment settings checked and completed."""
    if not isinstance(payload, dict):
        raise ValueError("Task must be a JSON object")
    task_id = payload.get("task_id")
    question = payload.get("question")
    file_name = payload.get("file_name") or ""
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id is required")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question is required")
    if not isinstance(file_name, str):
        raise ValueError("file_name must be a string")
    return {
        "task_id": task_id,
        "question": question,
        "file_name": file_name,
        "experiment": normalize_experiment(payload.get("experiment")),
    }


def _failed_run(status: int, error: Exception, started_at: float) -> JsonResponse:
    """The error, plus whatever the run recorded before failing."""
    return JsonResponse(
        status,
        {
            "error": str(error),
            "run_id": getattr(error, "run_id", None),
            "pipeline_version": getattr(error, "pipeline_version", None),
            "llm_duration_seconds": getattr(error, "llm_duration_seconds", None),
            "duration_seconds": round(perf_counter() - started_at, 3),
        },
    )


def run_task(request: Request) -> Response:
    """Run a GAIA task through the local LangGraph workflow."""
    started_at = perf_counter()
    try:
        result = run_pipeline(validate_task(request.json_value()))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return _failed_run(400, error, started_at)
    except Exception as error:
        return _failed_run(500, error, started_at)
    result["duration_seconds"] = round(perf_counter() - started_at, 3)
    return ok(result)


def get_run(request: Request) -> Response:
    try:
        return ok(read_record("runs", request.params["id"]))
    except (ValueError, FileNotFoundError):
        return failure(404, "Run not found")


def register(router: Router) -> None:
    router.add("POST", "/api/run")(run_task)
    router.add("GET", "/api/runs/{id*}")(get_run)
