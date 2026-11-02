"""The registry a Studio architecture is validated and compiled against."""

from huggingface_agents_langgraph.graph_definition.components.llm_roles import (
    register_llm_roles,
)
from huggingface_agents_langgraph.graph_definition.components.tools import (
    register_tool_components,
)
from huggingface_agents_langgraph.graph_definition.components.v31 import (
    create_gaia_v3_registry,
)
from huggingface_agents_langgraph.graph_definition.registry import NodeRegistry


def create_studio_registry() -> NodeRegistry:
    """The V3.1 components plus the configurable ones a Studio architecture may use."""
    registry = create_gaia_v3_registry()
    register_llm_roles(registry)
    register_tool_components(registry)
    return registry
