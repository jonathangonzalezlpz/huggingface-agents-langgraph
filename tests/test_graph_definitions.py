"""The declarative V3.1 definition must mirror the runtime graph topology."""

from huggingface_agents_langgraph.graph import build_state_graph
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.graph_definition.registry import (
    create_gaia_v3_registry,
)
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    create_gaia_v31_routing_registry,
)

START = "__start__"
END = "__end__"


def _definition_edges(definition):
    """(source, target, is_conditional) triples, with START written explicitly."""
    edges = {(START, definition.initial_node, False)}
    for edge in definition.edges:
        if edge.edge_type == "direct":
            edges.add((edge.source, edge.target, False))
        else:
            edges.update(
                (edge.source, target, True)
                for target in edge.conditional_targets.values()
            )
    return edges


def _runtime_graph():
    return build_state_graph().get_graph()


def test_node_ids_match_runtime_graph():
    declared = {node.id for node in create_gaia_v31_definition().nodes}
    assert declared == set(_runtime_graph().nodes) - {START, END}


def test_edges_match_runtime_graph():
    runtime = {
        (edge.source, edge.target, bool(edge.conditional))
        for edge in _runtime_graph().edges
    }
    assert _definition_edges(create_gaia_v31_definition()) == runtime


def test_conditional_labels_match_runtime_graph():
    definition = create_gaia_v31_definition()
    declared = {
        (edge.source, label): target
        for edge in definition.edges
        if edge.edge_type == "conditional"
        for label, target in edge.conditional_targets.items()
    }
    for edge in _runtime_graph().edges:
        if edge.conditional:
            assert declared[(edge.source, edge.data)] == edge.target


def test_every_node_uses_a_registered_implementation():
    registry = create_gaia_v3_registry()
    for node in create_gaia_v31_definition().nodes:
        assert registry.has(node.implementation_id)


def test_conditional_edges_use_registered_strategies():
    routing = create_gaia_v31_routing_registry()
    for edge in create_gaia_v31_definition().edges:
        if edge.edge_type == "conditional":
            assert routing.get(edge.routing_strategy).outputs == frozenset(
                edge.conditional_targets
            )


def test_definition_round_trips_through_dict():
    definition = create_gaia_v31_definition()
    assert type(definition).from_dict(definition.to_dict()) == definition
