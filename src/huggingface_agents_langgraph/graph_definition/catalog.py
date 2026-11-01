"""JSON-serializable catalog of what an editor may place in a graph."""

from collections.abc import Collection

from huggingface_agents_langgraph.graph_definition.registry import NodeRegistry
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    RoutingRegistry,
)

CATEGORIES = ("input", "acquisition", "research", "reasoning", "output")
UNCATEGORIZED = "other"


def build_catalog(
    node_registry: NodeRegistry,
    routing_registry: RoutingRegistry,
    *,
    state_types: Collection[str],
    state_fields: Collection[str],
    initial_fields: Collection[str],
) -> dict:
    """Describe components, routing strategies and state for editors and clients."""
    nodes = []
    for implementation_id in node_registry.list_implementations():
        registration = node_registry.get_registration(implementation_id)
        contract = registration.contract
        nodes.append(
            {
                "implementation_id": implementation_id,
                "description": registration.description,
                "category": registration.metadata.get("category", UNCATEGORIZED),
                "recover_errors": registration.recover_errors,
                "params": [spec.to_dict() for spec in registration.params],
                "contract": {
                    "required_inputs": sorted(contract.required_inputs),
                    "optional_inputs": sorted(contract.optional_inputs),
                    "guaranteed_outputs": sorted(contract.guaranteed_outputs),
                    "optional_outputs": sorted(contract.optional_outputs),
                },
            }
        )
    strategies = []
    for identifier in routing_registry.list_strategies():
        strategy = routing_registry.get(identifier)
        strategies.append(
            {
                "identifier": identifier,
                "description": strategy.description,
                "outputs": sorted(strategy.outputs),
            }
        )
    return {
        "categories": list(CATEGORIES),
        "nodes": nodes,
        "routing_strategies": strategies,
        "state": {
            "types": sorted(state_types),
            "fields": sorted(state_fields),
            "initial_fields": sorted(initial_fields),
        },
    }
