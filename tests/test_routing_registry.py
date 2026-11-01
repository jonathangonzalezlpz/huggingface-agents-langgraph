"""Tests for the closed registry of routing strategies."""

import pytest

from huggingface_agents_langgraph.graph_definition.routing_registry import (
    RoutingRegistry,
    RoutingStrategy,
    create_gaia_v31_routing_registry,
    resolve_routing_attr,
)


class TestRoutingStrategy:
    def test_outputs_are_frozen(self):
        strategy = RoutingStrategy("s", outputs={"a", "b"})
        assert strategy.outputs == frozenset({"a", "b"})

    def test_rejects_empty_identifier(self):
        with pytest.raises(ValueError, match="identifier"):
            RoutingStrategy(" ", outputs={"a"})

    def test_rejects_empty_outputs(self):
        with pytest.raises(ValueError, match="at least one"):
            RoutingStrategy("s", outputs=set())

    @pytest.mark.parametrize("label", ["", "  "])
    def test_rejects_blank_labels(self, label):
        with pytest.raises(ValueError, match="blank"):
            RoutingStrategy("s", outputs={"a", label})


class TestRoutingRegistry:
    def test_register_and_get(self):
        registry = RoutingRegistry()
        registry.register(RoutingStrategy("s", outputs={"a"}))
        assert registry.has("s")
        assert registry.get("s").outputs == frozenset({"a"})
        assert registry.list_strategies() == ["s"]

    def test_unknown_strategy_raises_key_error(self):
        with pytest.raises(KeyError, match="missing"):
            RoutingRegistry().get("missing")

    def test_duplicate_requires_override(self):
        registry = RoutingRegistry()
        registry.register(RoutingStrategy("s", outputs={"a"}))
        with pytest.raises(KeyError, match="already registered"):
            registry.register(RoutingStrategy("s", outputs={"b"}))
        registry.register(RoutingStrategy("s", outputs={"b"}), override=True)
        assert registry.get("s").outputs == frozenset({"b"})

    def test_rejects_non_strategy(self):
        with pytest.raises(TypeError):
            RoutingRegistry().register("s")  # type: ignore


def test_v31_catalog_matches_runtime_route_labels():
    registry = create_gaia_v31_routing_registry()
    assert registry.list_strategies() == [
        "route_after_preprocessing",
        "route_after_review",
        "route_after_router",
    ]
    assert registry.get("route_after_review").outputs == frozenset({"act", "solve"})
    assert registry.get("route_after_router").outputs == frozenset(
        {"code", "spreadsheet", "document", "multimedia", "web", "direct", "finish"}
    )
    assert registry.get("route_after_preprocessing").outputs == frozenset(
        {"resolve_attachment", "skip_attachment"}
    )


class TestRoutingResolution:
    def test_resolve_returns_the_lazily_resolved_callable(self):
        calls = []

        def resolver():
            calls.append(1)
            return lambda state: "left"

        registry = RoutingRegistry()
        registry.register(RoutingStrategy("s", outputs={"left"}, resolver=resolver))
        assert calls == []
        assert registry.resolve("s")({}) == "left"
        assert calls == [1]

    def test_strategy_without_resolver_cannot_be_resolved(self):
        registry = RoutingRegistry()
        registry.register(RoutingStrategy("s", outputs={"left"}))
        with pytest.raises(ValueError, match="no resolver"):
            registry.resolve("s")

    def test_unknown_strategy_cannot_be_resolved(self):
        with pytest.raises(KeyError):
            RoutingRegistry().resolve("missing")

    def test_non_callable_result_is_rejected(self):
        registry = RoutingRegistry()
        registry.register(RoutingStrategy("s", outputs={"a"}, resolver=lambda: 42))
        with pytest.raises(TypeError, match="non-callable"):
            registry.resolve("s")

    def test_unauthorized_attribute_is_rejected(self):
        with pytest.raises(PermissionError, match="Unauthorized"):
            resolve_routing_attr("os", "system")
        with pytest.raises(PermissionError):
            resolve_routing_attr(
                "huggingface_agents_langgraph.graph", "build_state_graph"
            )

    def test_v31_catalog_resolves_to_the_runtime_routing_functions(self):
        from huggingface_agents_langgraph import graph

        registry = create_gaia_v31_routing_registry()
        assert registry.resolve("route_after_router") is graph._route_after_router
        assert registry.resolve("route_after_review") is graph._route_after_review
        assert (
            registry.resolve("route_after_preprocessing")
            is graph._route_after_preprocessing
        )
