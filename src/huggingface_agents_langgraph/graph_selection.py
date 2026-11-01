"""Selection of the executable graph for an experiment.

Without an architecture reference the runtime graph in ``graph.py`` is used, so
existing experiments are unchanged. With a reference, the stored version is
compiled from its declarative definition.
"""

from langgraph.graph.state import CompiledStateGraph

from huggingface_agents_langgraph.architecture_store import (
    ArchitectureNotFoundError,
    get_architecture,
)
from huggingface_agents_langgraph.graph import build_state_graph
from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    GraphCompiler,
)
from huggingface_agents_langgraph.graph_definition.registry import (
    create_studio_registry,
)
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    create_studio_routing_registry,
)


def select_graph(experiment: dict) -> tuple[CompiledStateGraph, dict]:
    """Return the graph to execute and a description of how it was obtained."""
    reference = experiment.get("architecture")
    if reference is None:
        return build_state_graph(), {"engine": "graph.py"}
    try:
        record = get_architecture(reference)
    except ArchitectureNotFoundError as error:
        raise ValueError(f"Unknown architecture '{reference}'") from error
    definition = AgentDefinition.from_dict(record["definition"])
    compiler = GraphCompiler(create_studio_registry(), create_studio_routing_registry())
    graph = compiler.compile(definition)
    info = {
        "engine": "compiled",
        "id": record["id"],
        "architecture_id": record["architecture_id"],
        "version": record["version"],
        "content_sha256": record["content_sha256"],
    }
    params = compiler.resolved_params(definition)
    if params:
        info["node_params"] = params
    return graph, info
