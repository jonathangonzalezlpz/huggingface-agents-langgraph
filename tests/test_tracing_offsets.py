"""The trace records when each step and model call started and which node ran it."""

from time import sleep

from huggingface_agents_langgraph.tracing import (
    RunTrace,
    current_trace,
    traced_completion,
    traced_node,
)


def _run(function, *arguments):
    trace = RunTrace()
    token = current_trace.set(trace)
    try:
        function(*arguments)
    finally:
        current_trace.reset(token)
    return trace


def test_steps_record_their_start_offset():
    @traced_node
    def first(state):
        sleep(0.01)
        return {}

    @traced_node
    def second(state):
        return {}

    def both(state):
        first(state)
        second(state)

    trace = _run(both, {})

    offsets = [step["started_offset_seconds"] for step in trace.steps]
    assert offsets[0] >= 0 and offsets[1] >= offsets[0] + 0.01


def test_a_call_made_inside_a_node_records_that_node_and_its_offset():
    @traced_completion
    def complete(messages, **kwargs):
        return "ok"

    @traced_node
    def reason(state):
        complete([{"role": "user", "content": "q"}])
        return {}

    trace = _run(reason, {})

    call = trace.calls[0]
    assert call["node"] == "reason"
    assert call["started_offset_seconds"] >= 0


def test_a_call_outside_any_node_has_no_node():
    @traced_completion
    def complete(messages, **kwargs):
        return "ok"

    trace = _run(complete, [])

    assert trace.calls[0]["node"] is None


def test_the_current_node_is_cleared_when_the_node_fails():
    @traced_completion
    def complete(messages, **kwargs):
        return "ok"

    @traced_node
    def failing(state):
        raise ValueError("x")

    def attempt(state):
        try:
            failing(state)
        except ValueError:
            pass
        complete([])

    trace = _run(attempt, {})

    assert trace.calls[0]["node"] is None
