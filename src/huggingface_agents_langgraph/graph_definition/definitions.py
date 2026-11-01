"""Canonical declarative definitions of existing pipelines."""

from huggingface_agents_langgraph.graph_definition.schema import (
    AgentDefinition,
    EdgeDefinition,
    NodeDefinition,
)

SCHEMA_VERSION = "4.0"
ACQUISITION_NODES = (
    "code_processing",
    "spreadsheet_processing",
    "document_processing",
    "multimedia_processing",
    "web_research",
)
NODE_IDS = (
    "preprocessing",
    "attachment_resolver",
    "router",
    *ACQUISITION_NODES,
    "review",
    "research_action",
    "reasoning",
    "answer_production",
)


def create_gaia_v31_definition() -> AgentDefinition:
    """Declare the V3.1 pipeline with the topology of ``graph.py``."""
    nodes = tuple(NodeDefinition(id=name, implementation_id=name) for name in NODE_IDS)
    edges = (
        EdgeDefinition(
            source="preprocessing",
            edge_type="conditional",
            routing_strategy="route_after_preprocessing",
            conditional_targets={
                "resolve_attachment": "attachment_resolver",
                "skip_attachment": "router",
            },
        ),
        EdgeDefinition(source="attachment_resolver", target="router"),
        EdgeDefinition(
            source="router",
            edge_type="conditional",
            routing_strategy="route_after_router",
            conditional_targets={
                "code": "code_processing",
                "spreadsheet": "spreadsheet_processing",
                "document": "document_processing",
                "multimedia": "multimedia_processing",
                "web": "web_research",
                "direct": "review",
                "finish": "review",
            },
        ),
        *(EdgeDefinition(source=name, target="review") for name in ACQUISITION_NODES),
        EdgeDefinition(
            source="review",
            edge_type="conditional",
            routing_strategy="route_after_review",
            conditional_targets={"act": "research_action", "solve": "reasoning"},
        ),
        EdgeDefinition(source="research_action", target="review"),
        EdgeDefinition(source="reasoning", target="answer_production"),
        EdgeDefinition(source="answer_production", target="__end__"),
    )
    return AgentDefinition(
        schema_version=SCHEMA_VERSION,
        architecture_id="gaia_v31",
        state_type="AgentState",
        initial_node="preprocessing",
        nodes=nodes,
        edges=edges,
    )
