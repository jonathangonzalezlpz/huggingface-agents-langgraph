"""The declaratively compiled V3.1 graph must behave like ``graph.py``.

Node implementations are replaced by deterministic stubs, so no model, network or
benchmark is involved; routing functions and wrappers are the real ones.
"""

import pytest

from huggingface_agents_langgraph import graph as runtime_graph
from huggingface_agents_langgraph.experiments import normalize_experiment
from huggingface_agents_langgraph.graph_definition import GraphCompiler
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.graph_definition.registry import (
    create_gaia_v3_registry,
)
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    create_gaia_v31_routing_registry,
)
from huggingface_agents_langgraph.run_tracking import RunTrace, current_trace

RECURSION_LIMIT = 40


def _declarative_graph():
    return GraphCompiler(
        create_gaia_v3_registry(), create_gaia_v31_routing_registry()
    ).compile(create_gaia_v31_definition())


def _run(graph, task):
    trace = RunTrace()
    token = current_trace.set(trace)
    try:
        result = graph.invoke(task, config={"recursion_limit": RECURSION_LIMIT})
        error = None
    except Exception as exc:
        result, error = None, f"{type(exc).__name__}: {exc}"
    finally:
        current_trace.reset(token)
    steps = [
        {key: value for key, value in step.items() if key != "duration_seconds"}
        for step in trace.steps
    ]
    return result, error, steps


def _task(question="plain", file_name="", **experiment):
    return {
        "task_id": "t",
        "question": question,
        "file_name": file_name,
        "experiment": normalize_experiment(experiment or None),
    }


SCENARIOS = {
    "direct": _task(),
    "code_attachment": _task(file_name="x.py"),
    "web_with_research_loop": _task(question="web question"),
    "web_failure_is_recovered": _task(question="web FAIL"),
    "force_direct": _task(file_name="x.py", force_direct=True),
    "disabled_capability": _task(
        question="web question", enabled_capabilities=["code"]
    ),
}


def test_topology_matches_the_runtime_graph():
    declarative = _declarative_graph().get_graph()
    runtime = runtime_graph.build_state_graph().get_graph()

    def edges(graph):
        return {(e.source, e.target, bool(e.conditional), e.data) for e in graph.edges}

    assert set(declarative.nodes) == set(runtime.nodes)
    assert edges(declarative) == edges(runtime)


@pytest.mark.usefixtures("stubbed_nodes")
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_behavior_matches_the_runtime_graph(scenario):
    task = SCENARIOS[scenario]
    expected = _run(runtime_graph.build_state_graph(), task)
    actual = _run(_declarative_graph(), task)
    assert actual == expected
    assert expected[1] is None


@pytest.mark.usefixtures("stubbed_nodes")
def test_scenarios_exercise_the_wrappers_and_the_research_loop():
    recovered = _run(_declarative_graph(), SCENARIOS["web_failure_is_recovered"])
    assert any("search unavailable" in n for n in recovered[0]["research_notes"])
    assert any(step.get("error") for step in recovered[2])

    looped = _run(_declarative_graph(), SCENARIOS["web_with_research_loop"])
    assert looped[0]["research_steps"] == 2
    visits = [step["node"] for step in looped[2]]
    assert visits.count("review") == 3
    assert visits.count("research_action") == 2
