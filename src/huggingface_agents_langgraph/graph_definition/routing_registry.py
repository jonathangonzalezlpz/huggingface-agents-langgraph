"""Closed registry of routing strategies usable by conditional edges.

A strategy declares its identifier and the closed set of branch labels it can
return. The routing function itself is bound lazily through an authorized
resolver, so validation never imports runtime modules.
"""

import importlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

AUTHORIZED_ROUTING_CALLABLES: frozenset[tuple[str, str]] = frozenset(
    {
        ("huggingface_agents_langgraph.graph", "_route_after_preprocessing"),
        ("huggingface_agents_langgraph.graph", "_route_after_router"),
        ("huggingface_agents_langgraph.graph", "_route_after_review"),
    }
)

# Decisions of the configurable roles, which are not part of the V3.1 pipeline.
AUTHORIZED_ROLE_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {("huggingface_agents_langgraph.llm_roles", "route_on_verdict")}
)


def resolve_routing_attr(module_name: str, attr_name: str) -> Callable[..., Any]:
    """Resolve a pre-approved routing function; reject anything else."""
    if (
        module_name,
        attr_name,
    ) not in AUTHORIZED_ROUTING_CALLABLES | AUTHORIZED_ROLE_ROUTES:
        raise PermissionError(
            "Unauthorized routing attribute resolution attempt: "
            f"'{module_name}.{attr_name}'"
        )
    return getattr(importlib.import_module(module_name), attr_name)


@dataclass(frozen=True)
class RoutingStrategy:
    """Identifier and closed set of branch labels of a routing decision."""

    identifier: str
    outputs: frozenset[str]
    description: str = ""
    resolver: Callable[[], Callable[..., Any]] | None = field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        if not self.identifier or not self.identifier.strip():
            raise ValueError("Routing strategy identifier cannot be empty")
        outputs = frozenset(self.outputs)
        if not outputs:
            raise ValueError(
                f"Routing strategy '{self.identifier}' must declare at least one output"
            )
        if any(not label.strip() for label in outputs):
            raise ValueError(
                f"Routing strategy '{self.identifier}' declares a blank output label"
            )
        object.__setattr__(self, "outputs", outputs)


class RoutingRegistry:
    """Catalogue of the routing strategies a graph definition may reference."""

    def __init__(self) -> None:
        self._strategies: dict[str, RoutingStrategy] = {}

    def register(self, strategy: RoutingStrategy, *, override: bool = False) -> None:
        if not isinstance(strategy, RoutingStrategy):
            raise TypeError(
                f"Expected a RoutingStrategy, got {type(strategy).__name__}"
            )
        if strategy.identifier in self._strategies and not override:
            raise KeyError(
                f"Routing strategy '{strategy.identifier}' is already registered. "
                "Specify override=True to update."
            )
        self._strategies[strategy.identifier] = strategy

    def get(self, identifier: str) -> RoutingStrategy:
        if identifier not in self._strategies:
            raise KeyError(f"Routing strategy '{identifier}' is not registered")
        return self._strategies[identifier]

    def has(self, identifier: str) -> bool:
        return identifier in self._strategies

    def resolve(self, identifier: str) -> Callable[..., Any]:
        """Resolve and return the routing function of a registered strategy."""
        strategy = self.get(identifier)
        if strategy.resolver is None:
            raise ValueError(f"Routing strategy '{identifier}' has no resolver")
        resolved = strategy.resolver()
        if not callable(resolved):
            raise TypeError(
                f"Resolver for '{identifier}' returned non-callable "
                f"{type(resolved).__name__}"
            )
        return resolved

    def list_strategies(self) -> list[str]:
        """Return the sorted identifiers of all registered strategies."""
        return sorted(self._strategies)


def _strategy(
    identifier: str,
    outputs: Iterable[str],
    description: str,
    *,
    module: str = "huggingface_agents_langgraph.graph",
    function_name: str | None = None,
):
    name = function_name or "_" + identifier
    return RoutingStrategy(
        identifier,
        frozenset(outputs),
        description,
        resolver=lambda: resolve_routing_attr(module, name),
    )


def create_gaia_v31_routing_registry() -> RoutingRegistry:
    """Create a registry with the routing decisions of the V3.1 pipeline."""
    registry = RoutingRegistry()
    registry.register(
        _strategy(
            "route_after_preprocessing",
            ("resolve_attachment", "skip_attachment"),
            "Resolves the attachment only when the experiment allows it.",
        )
    )
    registry.register(
        _strategy(
            "route_after_router",
            (
                "code",
                "spreadsheet",
                "document",
                "multimedia",
                "web",
                "direct",
                "finish",
            ),
            "Sends the task to its source-specific node or straight to review.",
        )
    )
    registry.register(
        _strategy(
            "route_after_review",
            ("act", "solve"),
            "Continues researching or moves on to reasoning.",
        )
    )
    return registry


def create_studio_routing_registry() -> RoutingRegistry:
    """The V3.1 decisions plus the ones the configurable roles add."""
    registry = create_gaia_v31_routing_registry()
    registry.register(
        _strategy(
            "route_on_verdict",
            ("accept", "revise"),
            "Revises the draft while the verifier rejects it and revisions remain.",
            module="huggingface_agents_langgraph.llm_roles",
            function_name="route_on_verdict",
        )
    )
    return registry
