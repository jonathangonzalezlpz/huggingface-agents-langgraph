"""Catalog of components, routing strategies and state fields for editors."""

import json

from huggingface_agents_langgraph.architecture_store import get_catalog
from huggingface_agents_langgraph.graph_definition import (
    NodeContract,
    NodeRegistry,
    RoutingRegistry,
    RoutingStrategy,
)
from huggingface_agents_langgraph.graph_definition.catalog import (
    CATEGORIES,
    build_catalog,
)
from huggingface_agents_langgraph.graph_definition.registry import (
    create_gaia_v3_registry,
)
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    create_gaia_v31_routing_registry,
)


def _catalog():
    return build_catalog(
        create_gaia_v3_registry(),
        create_gaia_v31_routing_registry(),
        state_types=["AgentState"],
        state_fields=["question", "evidence"],
        initial_fields=["question"],
    )


def test_every_v31_component_has_a_known_category():
    nodes = _catalog()["nodes"]
    assert len(nodes) == 12
    assert {node["category"] for node in nodes} == set(CATEGORIES)


def test_categories_follow_the_pipeline_roles():
    by_id = {n["implementation_id"]: n["category"] for n in _catalog()["nodes"]}
    assert by_id["preprocessing"] == "input"
    assert by_id["router"] == "input"
    assert by_id["web_research"] == "acquisition"
    assert by_id["review"] == "research"
    assert by_id["research_action"] == "research"
    assert by_id["reasoning"] == "reasoning"
    assert by_id["answer_production"] == "output"


def test_components_expose_contract_and_error_recovery():
    nodes = {n["implementation_id"]: n for n in _catalog()["nodes"]}
    web = nodes["web_research"]
    assert web["recover_errors"] is True
    assert web["contract"]["required_inputs"] == ["question"]
    assert web["contract"]["optional_outputs"] == ["evidence", "research_notes"]
    assert nodes["router"]["recover_errors"] is False
    assert nodes["router"]["description"]


def test_routing_strategies_list_their_branches_sorted():
    strategies = {s["identifier"]: s for s in _catalog()["routing_strategies"]}
    assert strategies["route_after_review"]["outputs"] == ["act", "solve"]
    assert strategies["route_after_router"]["outputs"] == sorted(
        strategies["route_after_router"]["outputs"]
    )


def test_state_section_and_determinism():
    catalog = _catalog()
    assert catalog["state"] == {
        "types": ["AgentState"],
        "fields": ["evidence", "question"],
        "initial_fields": ["question"],
    }
    assert catalog["categories"] == list(CATEGORIES)
    assert [n["implementation_id"] for n in catalog["nodes"]] == sorted(
        n["implementation_id"] for n in catalog["nodes"]
    )
    assert json.dumps(_catalog()) == json.dumps(_catalog())


def test_uncategorized_components_are_reported_as_other():
    registry = NodeRegistry()
    registry.register("custom", NodeContract(), handler=lambda state: {})
    routing = RoutingRegistry()
    routing.register(RoutingStrategy("s", outputs={"a"}))
    catalog = build_catalog(
        registry, routing, state_types=[], state_fields=[], initial_fields=[]
    )
    assert catalog["nodes"][0]["category"] == "other"


def test_default_catalog_uses_the_real_state_schema():
    catalog = get_catalog()
    assert catalog["state"]["types"] == ["AgentState"]
    assert "question" in catalog["state"]["fields"]
    assert set(catalog["state"]["initial_fields"]) == {
        "task_id",
        "question",
        "file_name",
    }
