"""Compilation of validated agent definitions into LangGraph state graphs."""

from collections.abc import Callable, Collection, Mapping
from functools import wraps
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from huggingface_agents_langgraph.graph_definition.diagnostics import (
    ValidationReport,
)
from huggingface_agents_langgraph.graph_definition.registry import NodeRegistry
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    RoutingRegistry,
)
from huggingface_agents_langgraph.graph_definition.schema import (
    SPECIAL_TERMINALS,
    START_TERMINALS,
    AgentDefinition,
    NodeDefinition,
    _unfreeze_metadata,
)
from huggingface_agents_langgraph.graph_definition.validator import GraphValidator
from huggingface_agents_langgraph.run_tracking import traced_node
from huggingface_agents_langgraph.state import AgentState

RECOVERABLE_ERRORS = (ValueError, RuntimeError, OSError)
END_TERMINALS = SPECIAL_TERMINALS - START_TERMINALS


class GraphCompilationError(ValueError):
    """Raised when a definition fails validation and cannot be compiled."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        codes = sorted({d.code for d in report.errors})
        super().__init__(f"Agent definition is invalid: {', '.join(codes)}")


def _recover_errors(function: Callable[..., Any]) -> Callable[..., Any]:
    """Turn recoverable acquisition failures into a research note."""

    @wraps(function)
    def wrapped(state):
        try:
            return function(state)
        except RECOVERABLE_ERRORS as error:
            return {
                "research_notes": [
                    *state.get("research_notes", []),
                    f"{function.__name__}: {error}",
                ]
            }

    return wrapped


def _named(handler: Callable[..., Any], name: str) -> Callable[..., Any]:
    """Run ``handler`` under the node id, so traces name the node, not its component."""

    @wraps(handler)
    def named(state):
        return handler(state)

    named.__name__ = name
    return named


def _target(name: str) -> str:
    return END if name in END_TERMINALS else name


class GraphCompiler:
    """Translate an ``AgentDefinition`` into an executable ``StateGraph``."""

    def __init__(
        self,
        node_registry: NodeRegistry,
        routing_registry: RoutingRegistry,
        *,
        state_types: Mapping[str, type] | None = None,
        validator: GraphValidator | None = None,
    ) -> None:
        self._nodes = node_registry
        self._routing = routing_registry
        self._state_types: Mapping[str, type] = (
            {AgentState.__name__: AgentState} if state_types is None else state_types
        )
        self._validator = validator or GraphValidator(
            node_registry,
            routing_registry,
            state_types=self._known_state_types(state_types),
        )

    @staticmethod
    def _known_state_types(
        state_types: Mapping[str, type] | None,
    ) -> Collection[str] | None:
        return None if state_types is None else list(state_types)

    def compile(self, definition: AgentDefinition) -> CompiledStateGraph:
        """Validate the definition and build its compiled LangGraph workflow."""
        report = self._validator.validate(definition)
        if not report.is_valid:
            raise GraphCompilationError(report)

        graph = StateGraph(self._state_types[definition.state_type])
        for node in definition.nodes:
            graph.add_node(node.id, self._wrapped_handler(node))

        graph.add_edge(START, definition.initial_node)
        for edge in definition.edges:
            if edge.source in START_TERMINALS:
                continue
            if edge.edge_type == "direct":
                graph.add_edge(edge.source, _target(edge.target or ""))
            else:
                graph.add_conditional_edges(
                    edge.source,
                    self._routing.resolve(edge.routing_strategy or ""),
                    {
                        label: _target(target)
                        for label, target in edge.conditional_targets.items()
                    },
                )
        return graph.compile()

    def resolved_params(self, definition: AgentDefinition) -> dict[str, dict[str, Any]]:
        """The parameters each configurable node will run with, defaults included.

        Recorded with a run so it stays reproducible even if a default changes later.
        """
        resolved: dict[str, dict[str, Any]] = {}
        for node in definition.nodes:
            registration = self._nodes.get_registration(node.implementation_id)
            if registration.params:
                resolved[node.id] = registration.resolve_params(
                    _unfreeze_metadata(node.params)
                )
        return resolved

    def _wrapped_handler(self, node: NodeDefinition) -> Callable[..., Any]:
        registration = self._nodes.get_registration(node.implementation_id)
        configured = registration.build_handler(_unfreeze_metadata(node.params))
        handler = traced_node(_named(configured, node.id))
        return _recover_errors(handler) if registration.recover_errors else handler
