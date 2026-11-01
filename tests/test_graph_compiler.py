"""Tests for compiling validated agent definitions into LangGraph."""

from dataclasses import replace

import pytest

from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    EdgeDefinition,
    GraphCompilationError,
    GraphCompiler,
    NodeContract,
    NodeDefinition,
    NodeRegistry,
    RoutingRegistry,
    RoutingStrategy,
)
from huggingface_agents_langgraph.run_tracking import RunTrace, current_trace

TASK = {"task_id": "t", "question": "q", "file_name": ""}


def _node(name, update=None, error=None):
    def run(state):
        if error is not None:
            raise error
        return dict(update or {})

    run.__name__ = name
    return run


def _registry(nodes):
    """nodes: name -> (handler, contract, recover_errors)."""
    registry = NodeRegistry()
    for name, (handler, contract, recover) in nodes.items():
        registry.register(name, contract, handler=handler, recover_errors=recover)
    return registry


def _routing(chooser=None):
    routing = RoutingRegistry()
    choose = chooser or (lambda state: "left")
    routing.register(
        RoutingStrategy("pick", outputs={"left", "right"}, resolver=lambda: choose)
    )
    return routing


def _definition(nodes, edges, initial=None):
    return AgentDefinition(
        schema_version="4.0",
        architecture_id="test",
        state_type="AgentState",
        initial_node=initial or nodes[0],
        nodes=tuple(NodeDefinition(id=n, implementation_id=n) for n in nodes),
        edges=tuple(edges),
    )


def _direct(source, target):
    return EdgeDefinition(source=source, target=target)


def _pick(source, left, right):
    return EdgeDefinition(
        source=source,
        edge_type="conditional",
        routing_strategy="pick",
        conditional_targets={"left": left, "right": right},
    )


def _compile(nodes, edges, chooser=None, initial=None):
    registry = _registry(nodes)
    definition = _definition(list(nodes), edges, initial)
    return GraphCompiler(registry, _routing(chooser)).compile(definition)


def _plain(handler, contract=None):
    return (handler, contract or NodeContract(), False)


@pytest.fixture
def trace():
    run_trace = RunTrace()
    token = current_trace.set(run_trace)
    yield run_trace
    current_trace.reset(token)


class TestExecution:
    def test_linear_graph_runs_in_order(self):
        order = []

        def first(state):
            order.append("first")
            return {"draft_answer": "d"}

        def second(state):
            order.append("second")
            return {"submitted_answer": state["draft_answer"]}

        graph = _compile(
            {"first": _plain(first), "second": _plain(second)},
            [_direct("first", "second"), _direct("second", "__end__")],
        )
        result = graph.invoke(TASK)
        assert order == ["first", "second"]
        assert result["submitted_answer"] == "d"

    @pytest.mark.parametrize("branch", ["left", "right"])
    def test_conditional_edge_follows_the_routing_function(self, branch):
        visited = []

        def mark(name):
            def run(state):
                visited.append(name)
                return {}

            run.__name__ = name
            return run

        graph = _compile(
            {
                "start": _plain(mark("start")),
                "left": _plain(mark("left")),
                "right": _plain(mark("right")),
            },
            [
                _pick("start", "left", "right"),
                _direct("left", "__end__"),
                _direct("right", "END"),
            ],
            chooser=lambda state: branch,
        )
        graph.invoke(TASK)
        assert visited == ["start", branch]

    def test_cycle_runs_until_the_routing_function_exits(self):
        def loop(state):
            return {"research_steps": state.get("research_steps", 0) + 1}

        graph = _compile(
            {
                "loop": _plain(
                    loop, NodeContract(guaranteed_outputs={"research_steps"})
                ),
                "gate": _plain(_node("gate")),
            },
            [_direct("loop", "gate"), _pick("gate", "loop", "__end__")],
            chooser=lambda state: "right" if state["research_steps"] >= 3 else "left",
        )
        assert graph.invoke(TASK)["research_steps"] == 3

    def test_initial_node_is_the_entry_point(self):
        order = []

        def mark(name):
            def run(state):
                order.append(name)
                return {}

            run.__name__ = name
            return run

        graph = _compile(
            {"a": _plain(mark("a")), "b": _plain(mark("b"))},
            [_direct("b", "a"), _direct("a", "__end__")],
            initial="b",
        )
        graph.invoke(TASK)
        assert order == ["b", "a"]


class TestCompilationGate:
    def test_invalid_definition_raises_with_the_report(self):
        registry = _registry({"a": _plain(_node("a"))})
        definition = _definition(["a"], [])
        with pytest.raises(GraphCompilationError) as error:
            GraphCompiler(registry, _routing()).compile(definition)
        assert "NO_PATH_TO_END" in {d.code for d in error.value.report.errors}
        assert isinstance(error.value, ValueError)

    def test_warnings_do_not_block_compilation(self):
        nodes = {
            "a": _plain(_node("a"), NodeContract(optional_outputs={"evidence"})),
            "b": _plain(_node("b"), NodeContract(required_inputs={"evidence"})),
        }
        registry = _registry(nodes)
        definition = _definition(["a", "b"], [_direct("a", "b"), _direct("b", "END")])
        graph = GraphCompiler(registry, _routing()).compile(definition)
        assert graph.invoke(TASK)["question"] == "q"

    def test_unknown_state_type_is_rejected(self):
        registry = _registry({"a": _plain(_node("a"))})
        definition = replace(
            _definition(["a"], [_direct("a", "END")]), state_type="Other"
        )
        with pytest.raises(GraphCompilationError) as error:
            GraphCompiler(registry, _routing()).compile(definition)
        assert error.value.report.errors[0].code == "UNKNOWN_STATE_TYPE"

    def test_start_edge_matching_initial_node_is_accepted(self):
        registry = _registry({"a": _plain(_node("a"))})
        definition = _definition(
            ["a"], [_direct("__start__", "a"), _direct("a", "END")]
        )
        graph = GraphCompiler(registry, _routing()).compile(definition)
        assert graph.invoke(TASK)["task_id"] == "t"


class TestWrappers:
    def test_every_node_is_traced(self, trace):
        graph = _compile(
            {
                "a": _plain(_node("a", {"draft_answer": "d"})),
                "b": _plain(_node("b")),
            },
            [_direct("a", "b"), _direct("b", "END")],
        )
        graph.invoke(TASK)
        assert [step["node"] for step in trace.steps] == ["a", "b"]
        assert trace.steps[0]["update"] == {"draft_answer": "d"}

    @pytest.mark.parametrize(
        "error", [ValueError("v"), RuntimeError("r"), OSError("o")]
    )
    def test_recoverable_node_turns_known_errors_into_notes(self, trace, error):
        graph = _compile(
            {
                "acquire": (
                    _node("acquire", error=error),
                    NodeContract(optional_outputs={"research_notes"}),
                    True,
                ),
                "after": _plain(_node("after")),
            },
            [_direct("acquire", "after"), _direct("after", "END")],
        )
        result = graph.invoke({**TASK, "research_notes": ["earlier"]})
        assert result["research_notes"] == ["earlier", f"acquire: {error}"]
        assert [step["node"] for step in trace.steps] == ["acquire", "after"]
        assert trace.steps[0]["error"] == str(error)

    def test_recoverable_node_does_not_hide_other_errors(self):
        graph = _compile(
            {
                "acquire": (
                    _node("acquire", error=KeyError("k")),
                    NodeContract(optional_outputs={"research_notes"}),
                    True,
                )
            },
            [_direct("acquire", "END")],
        )
        with pytest.raises(KeyError):
            graph.invoke(TASK)

    def test_node_without_recovery_propagates_errors(self, trace):
        graph = _compile(
            {"a": _plain(_node("a", error=ValueError("boom")))},
            [_direct("a", "END")],
        )
        with pytest.raises(ValueError, match="boom"):
            graph.invoke(TASK)
        assert trace.steps[0]["error"] == "boom"
