"""Run one task through the selected graph, keeping its trace even when a node fails."""

import hashlib
import json
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from huggingface_agents_langgraph.adapters.records import write_record
from huggingface_agents_langgraph.config import (
    LLM_FINAL_ANSWER_MAX_TOKENS,
    LLM_REASONING_MAX_TOKENS,
    MEDIA_ASR_MODEL,
    MEDIA_VLM_MODEL,
    MODEL_SERVER_MODE,
    PIPELINE_MAX_ACTIONS,
    PIPELINE_MAX_LLM_CALLS,
    PIPELINE_TIMEOUT_SECONDS,
)
from huggingface_agents_langgraph.domain.experiments import normalize_experiment
from huggingface_agents_langgraph.tracing import RunTrace, current_trace


def run_pipeline(task: dict) -> dict:
    """Execute the graph and retain its trace even when a node fails."""
    from huggingface_agents_langgraph.application.graph_selection import select_graph

    task = task | {"experiment": normalize_experiment(task.get("experiment"))}
    version = task["experiment"]["pipeline_version"]
    trace = RunTrace(experiment=task["experiment"])
    token = current_trace.set(trace)
    monitor = None
    if MODEL_SERVER_MODE == "exclusive":
        from huggingface_agents_langgraph.adapters.resource_tracking import (
            ResourceMonitor,
        )

        monitor = ResourceMonitor()
        monitor.start()
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
        "models": {
            "vision": task["experiment"].get("vision_model") or MEDIA_VLM_MODEL,
            "reasoner": task["experiment"].get("model"),
            "transcription": MEDIA_ASR_MODEL,
            "server_mode": MODEL_SERVER_MODE,
        },
    }
    try:
        graph, record["architecture"] = select_graph(task["experiment"])
        result = graph.invoke(task, config={"recursion_limit": 40})
        record["result"] = result
        record["status"] = "completed"
        return result | {
            "pipeline_version": version,
            "run_id": record["id"],
            "duration_seconds": round(perf_counter() - trace.started, 3),
            "llm_duration_seconds": round(
                sum(call["duration_seconds"] for call in trace.calls), 3
            ),
            "model_load_seconds": round(
                sum(call.get("model_load_seconds", 0) for call in trace.calls), 3
            ),
            "resources": dict(monitor.metrics) if monitor else {},
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
            resources=monitor.finish() if monitor else {},
        )
        current_trace.reset(token)
        write_record("runs", record)
