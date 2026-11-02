"""Component catalogues: what can be placed in a declared architecture."""

from huggingface_agents_langgraph.graph_definition.components.studio import (
    create_studio_registry,
)
from huggingface_agents_langgraph.graph_definition.components.v31 import (
    create_gaia_v3_registry,
)

__all__ = ["create_gaia_v3_registry", "create_studio_registry"]
