"""Per-run tracing: what each node and model call did, and how long a run may take."""

from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from functools import wraps
from time import perf_counter

from huggingface_agents_langgraph.config import (
    PIPELINE_MAX_LLM_CALLS,
    PIPELINE_TIMEOUT_SECONDS,
)


@dataclass
class RunTrace:
    """Data isolated to the current question's execution context."""

    started: float = field(default_factory=perf_counter)
    calls: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    experiment: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    current_node: str | None = None


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
        if trace is not None:
            step["started_offset_seconds"] = round(started - trace.started, 4)
            trace.current_node = function.__name__
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
                trace.current_node = None
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
        started = perf_counter()
        if trace is not None:
            call["node"] = trace.current_node
            call["started_offset_seconds"] = round(started - trace.started, 4)
            trace.calls.append(call)
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
