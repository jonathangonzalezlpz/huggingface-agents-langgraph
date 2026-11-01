"""Declarative contracts and registry for GAIA Agent V4 workflows."""

from huggingface_agents_langgraph.graph_definition.contracts import NodeContract
from huggingface_agents_langgraph.graph_definition.registry import (
    NodeRegistration,
    NodeRegistry,
)
from huggingface_agents_langgraph.graph_definition.schema import (
    AgentDefinition,
    EdgeDefinition,
    NodeDefinition,
)

__all__ = [
    "AgentDefinition",
    "EdgeDefinition",
    "NodeContract",
    "NodeDefinition",
    "NodeRegistration",
    "NodeRegistry",
]
