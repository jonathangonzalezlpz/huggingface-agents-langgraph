"""Registry of node implementations and their contracts.

A ``NodeRegistration`` binds an implementation id to its contract, its parameters
and the way to obtain its handler (a handler, a lazy resolver or a builder). The
registry holds no components of its own: see ``graph_definition.components``.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from huggingface_agents_langgraph.graph_definition.contracts import NodeContract
from huggingface_agents_langgraph.graph_definition.params import (
    ParamError,
    ParamSpec,
    check_params,
    resolve_params,
)
from huggingface_agents_langgraph.graph_definition.schema import _freeze_metadata


@dataclass(frozen=True)
class NodeRegistration:
    """Authorized node registration with contract, handler/resolver, and metadata."""

    implementation_id: str
    contract: NodeContract
    handler: Callable[..., Any] | None = None
    resolver: Callable[[], Callable[..., Any]] | None = None
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    recover_errors: bool = False
    # Parameterized components: ``builder(resolved_params)`` returns the node handler.
    builder: Callable[[Mapping[str, Any]], Callable[..., Any]] | None = None
    params: tuple[ParamSpec, ...] = ()

    def __post_init__(self) -> None:
        if not self.implementation_id or not self.implementation_id.strip():
            raise ValueError("implementation_id cannot be empty")
        ways = [self.handler, self.resolver, self.builder]
        if sum(way is not None for way in ways) == 0:
            raise ValueError(
                f"Registration '{self.implementation_id}' must provide "
                "a handler, a resolver or a builder"
            )
        if self.builder is not None:
            if self.handler is not None or self.resolver is not None:
                raise ValueError(
                    f"Registration '{self.implementation_id}' cannot combine a "
                    "builder with a handler or resolver"
                )
            if not callable(self.builder):
                raise TypeError(
                    f"Builder for '{self.implementation_id}' must be callable"
                )
            if not self.params:
                raise ValueError(
                    f"Registration '{self.implementation_id}' has a builder "
                    "but declares no parameters"
                )
        object.__setattr__(self, "params", tuple(self.params))
        names = [spec.name for spec in self.params]
        if len(set(names)) != len(names):
            raise ValueError(
                f"Registration '{self.implementation_id}' repeats a parameter name"
            )
        if self.handler is not None and not callable(self.handler):
            raise TypeError(f"Handler for '{self.implementation_id}' must be callable")
        if self.resolver is not None and not callable(self.resolver):
            raise TypeError(f"Resolver for '{self.implementation_id}' must be callable")
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def check_params(self, params: Mapping[str, Any]) -> list[ParamError]:
        """Every problem with the given parameter values, without raising."""
        return check_params(self.params, params)

    def resolve_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """The given values with defaults filled in; raises ``ParamError``."""
        return resolve_params(self.params, params)

    def build_handler(
        self, params: Mapping[str, Any] | None = None
    ) -> Callable[..., Any]:
        """The node handler configured with ``params`` (defaults applied)."""
        resolved = self.resolve_params(params or {})
        if self.builder is None:
            return self.resolve_handler()
        handler = self.builder(resolved)
        if not callable(handler):
            raise TypeError(
                f"Builder for '{self.implementation_id}' returned "
                f"non-callable {type(handler).__name__}"
            )
        return handler

    def resolve_handler(self) -> Callable[..., Any]:
        """Resolve and return the callable node implementation."""
        if self.resolver is not None:
            resolved = self.resolver()
            if not callable(resolved):
                cls_name = type(resolved).__name__
                raise TypeError(
                    f"Resolver for '{self.implementation_id}' returned "
                    f"non-callable {cls_name}"
                )
            return resolved
        assert self.handler is not None
        return self.handler


class NodeRegistry:
    """Registry of authorized node implementations.

    Prevents arbitrary code execution by maintaining an explicit catalogue
    of authorized implementations. Instances are decoupled to facilitate
    testing and dependency injection without mandatory global singletons.
    """

    def __init__(self) -> None:
        self._registry: dict[str, NodeRegistration] = {}

    def register(
        self,
        implementation_id: str,
        contract: NodeContract,
        *,
        handler: Callable[..., Any] | None = None,
        resolver: Callable[[], Callable[..., Any]] | None = None,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
        recover_errors: bool = False,
        builder: Callable[[Mapping[str, Any]], Callable[..., Any]] | None = None,
        params: Sequence[ParamSpec] = (),
        override: bool = False,
    ) -> None:
        """Register an authorized node implementation with its contract."""
        if not implementation_id or not implementation_id.strip():
            raise ValueError("implementation_id cannot be empty")
        if not isinstance(contract, NodeContract):
            contract_type = type(contract).__name__
            raise TypeError(
                f"Contract for '{implementation_id}' must be a NodeContract "
                f"instance, got {contract_type}"
            )
        if implementation_id in self._registry and not override:
            raise KeyError(
                f"Implementation '{implementation_id}' is already registered. "
                "Specify override=True to update."
            )

        self._registry[implementation_id] = NodeRegistration(
            implementation_id=implementation_id,
            contract=contract,
            handler=handler,
            resolver=resolver,
            description=description,
            metadata=dict(metadata or {}),
            recover_errors=recover_errors,
            builder=builder,
            params=tuple(params),
        )

    def get_registration(self, implementation_id: str) -> NodeRegistration:
        """Retrieve registration metadata for a given implementation ID."""
        if implementation_id not in self._registry:
            raise KeyError(f"Implementation '{implementation_id}' is not registered")
        return self._registry[implementation_id]

    def get_contract(self, implementation_id: str) -> NodeContract:
        """Retrieve contract without invoking or resolving the handler."""
        return self.get_registration(implementation_id).contract

    def resolve(self, implementation_id: str) -> Callable[..., Any]:
        """Resolve and return the callable handler for the node."""
        return self.get_registration(implementation_id).resolve_handler()

    def list_implementations(self) -> list[str]:
        """Return sorted list of all registered implementation IDs."""
        return sorted(self._registry.keys())

    def has(self, implementation_id: str) -> bool:
        """Check whether an implementation ID is registered."""
        return implementation_id in self._registry

    def unregister(self, implementation_id: str) -> None:
        """Remove an implementation from the registry."""
        if implementation_id in self._registry:
            del self._registry[implementation_id]
