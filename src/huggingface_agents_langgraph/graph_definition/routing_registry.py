"""Closed registry of routing strategies usable by conditional edges.

A strategy declares only its identifier and the closed set of branch labels it
can return. Binding to the runtime routing functions is the compiler's concern.
"""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingStrategy:
    """Identifier and closed set of branch labels of a routing decision."""

    identifier: str
    outputs: frozenset[str]
    description: str = ""

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

    def list_strategies(self) -> list[str]:
        """Return the sorted identifiers of all registered strategies."""
        return sorted(self._strategies)


def _strategy(identifier: str, outputs: Iterable[str], description: str):
    return RoutingStrategy(identifier, frozenset(outputs), description)


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
