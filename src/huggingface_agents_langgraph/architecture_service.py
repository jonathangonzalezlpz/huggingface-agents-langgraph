"""Use cases around architectures: validate them, read them with their report, and
describe the catalog an editor may build from."""

from typing import Any

from huggingface_agents_langgraph.architecture_store import get_architecture
from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    Diagnostic,
    GraphValidator,
    ValidationReport,
)
from huggingface_agents_langgraph.graph_definition.catalog import build_catalog
from huggingface_agents_langgraph.graph_definition.components import (
    create_studio_registry,
)
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    create_studio_routing_registry,
)
from huggingface_agents_langgraph.state import AgentState


def _validator() -> GraphValidator:
    return GraphValidator(create_studio_registry(), create_studio_routing_registry())


def validate_definition(payload: Any) -> dict:
    """Validate a serialized definition, reporting structural problems as findings."""
    try:
        definition = AgentDefinition.from_dict(payload)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        message = (
            f"Missing field {error}" if isinstance(error, KeyError) else str(error)
        )
        report = ValidationReport((Diagnostic("INVALID_DEFINITION", "error", message),))
        return report.to_dict()
    return _validator().validate(definition).to_dict()


def architecture_detail(identifier: str) -> dict:
    """A stored version together with its current validation report."""
    record = get_architecture(identifier)
    return {**record, "validation": validate_definition(record["definition"])}


def get_catalog() -> dict:
    """Components, routing strategies and state schema available for graphs."""
    return build_catalog(
        create_studio_registry(),
        create_studio_routing_registry(),
        state_types=[AgentState.__name__],
        state_fields=AgentState.__annotations__,
        initial_fields=AgentState.__required_keys__,
    )
