"""Per-run tracing, bounded execution, and local JSON persistence."""

import hashlib
import json
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from huggingface_agents_langgraph.config import (
    LLM_FINAL_ANSWER_MAX_TOKENS,
    LLM_REASONING_MAX_TOKENS,
    MEDIA_ASR_MODEL,
    MEDIA_VLM_MODEL,
    PIPELINE_MAX_ACTIONS,
    PIPELINE_MAX_LLM_CALLS,
    PIPELINE_TIMEOUT_SECONDS,
    RUNTIME_DIRECTORY,
)
from huggingface_agents_langgraph.experiments import normalize_experiment
from huggingface_agents_langgraph.pipeline_versions import V2_REFERENCE_ID


@dataclass
class RunTrace:
    """Data isolated to the current question's execution context."""

    started: float = field(default_factory=perf_counter)
    calls: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    experiment: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)


current_trace: ContextVar[RunTrace | None] = ContextVar("run_trace", default=None)


def remaining_seconds() -> float:
    """Return the remaining wall-time allowance for the current run."""
    trace = current_trace.get()
    return (
        max(0, PIPELINE_TIMEOUT_SECONDS - (perf_counter() - trace.started))
        if trace
        else float(PIPELINE_TIMEOUT_SECONDS)
    )


def traced_node(function):
    """Record node updates and errors without sharing mutable graph state."""

    @wraps(function)
    def wrapped(state):
        trace = current_trace.get()
        started = perf_counter()
        step = {"node": function.__name__}
        try:
            if remaining_seconds() <= 0:
                raise TimeoutError("Pipeline time budget exhausted")
            update = function(state)
            step["update"] = update
            return update
        except Exception as error:
            step["error"] = str(error)
            raise
        finally:
            step["duration_seconds"] = round(perf_counter() - started, 4)
            if trace is not None:
                trace.steps.append(step)

    return wrapped


def check_call_budget() -> None:
    """Reject calls that exceed the configured run allowance."""
    trace = current_trace.get()
    if remaining_seconds() <= 0:
        raise TimeoutError("Pipeline time budget exhausted")
    if trace and len(trace.calls) >= PIPELINE_MAX_LLM_CALLS:
        raise RuntimeError("Pipeline model-call budget exhausted")


def traced_completion(function):
    """Capture model inputs, output, timing, and failed calls."""

    @wraps(function)
    def wrapped(messages, **kwargs):
        check_call_budget()
        trace = current_trace.get()
        call = {"messages": deepcopy(messages), "parameters": deepcopy(kwargs)}
        if trace is not None:
            trace.calls.append(call)
        started = perf_counter()
        try:
            output = function(messages, **kwargs)
            call["content"] = output
            return output
        except Exception as error:
            call["error"] = str(error)
            raise
        finally:
            call["duration_seconds"] = round(perf_counter() - started, 4)

    return wrapped


def write_record(kind: str, record: dict) -> None:
    """Atomically store a record under its UUID in the runtime directory."""
    record_id = str(UUID(record["id"]))
    directory = Path(RUNTIME_DIRECTORY) / kind
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{record_id}.json"
    if kind == "experiments" and record_id == V2_REFERENCE_ID and destination.exists():
        original = json.loads(destination.read_text(encoding="utf-8"))
        if any(record.get(key) != value for key, value in original.items()):
            raise ValueError("The V2 reference is immutable; save a new experiment")
        return
    temporary = directory / f".{record_id}.{uuid4()}.tmp"
    temporary.write_text(
        json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8"
    )
    temporary.replace(destination)


def read_record(kind: str, record_id: str) -> dict:
    """Load a UUID-addressed runtime record."""
    path = Path(RUNTIME_DIRECTORY) / kind / f"{UUID(record_id)}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_records(kind: str) -> list[dict]:
    """Load locally persisted records, newest first."""
    directory = Path(RUNTIME_DIRECTORY) / kind
    records = []
    for path in directory.glob("*.json"):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)


def delete_record(kind: str, record_id: str) -> None:
    """Delete only the selected UUID-addressed record."""
    if kind == "experiments" and str(UUID(record_id)) == V2_REFERENCE_ID:
        raise ValueError("The V2 reference cannot be deleted from the experiment panel")
    (Path(RUNTIME_DIRECTORY) / kind / f"{UUID(record_id)}.json").unlink(missing_ok=True)


def run_pipeline(task: dict) -> dict:
    """Execute the graph and retain its trace even when a node fails."""
    from huggingface_agents_langgraph.graph import build_state_graph

    task = task | {"experiment": normalize_experiment(task.get("experiment"))}
    version = task["experiment"]["pipeline_version"]
    trace = RunTrace(experiment=task["experiment"])
    token = current_trace.set(trace)
    record = {
        "id": str(uuid4()),
        "pipeline_version": version,
        "configuration_sha256": hashlib.sha256(
            json.dumps(task["experiment"], sort_keys=True).encode()
        ).hexdigest(),
        "created_at": datetime.now(UTC).isoformat(),
        "task": task,
        "limits": {
            "seconds": PIPELINE_TIMEOUT_SECONDS,
            "llm_calls": PIPELINE_MAX_LLM_CALLS,
            "tool_actions": PIPELINE_MAX_ACTIONS,
            "reasoning_tokens": LLM_REASONING_MAX_TOKENS,
            "answer_tokens": LLM_FINAL_ANSWER_MAX_TOKENS,
        },
        "models": {"vision": MEDIA_VLM_MODEL, "transcription": MEDIA_ASR_MODEL},
    }
    try:
        result = build_state_graph().invoke(task, config={"recursion_limit": 40})
        record["result"] = result
        record["status"] = "completed"
        return result | {
            "pipeline_version": version,
            "run_id": record["id"],
            "duration_seconds": round(perf_counter() - trace.started, 3),
            "llm_duration_seconds": round(
                sum(call["duration_seconds"] for call in trace.calls), 3
            ),
        }
    except Exception as error:
        record["error"] = str(error)
        record["status"] = "error"
        error.run_id = record["id"]
        error.pipeline_version = version
        error.llm_duration_seconds = round(
            sum(call["duration_seconds"] for call in trace.calls), 3
        )
        raise
    finally:
        record.update(
            steps=trace.steps,
            calls=trace.calls,
            sources=trace.sources,
            duration_seconds=round(perf_counter() - trace.started, 3),
        )
        current_trace.reset(token)
        write_record("runs", record)
