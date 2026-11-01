"""Authorized node registry and dependency injection container.

Maintains an explicit, approved catalogue of node contracts and implementations.
Rejects arbitrary runtime imports and code execution, while supporting dependency
injection and lazy handler resolution to play cleanly with test mocking.
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

# Exact whitelist of approved internal node implementations
AUTHORIZED_CALLABLES: frozenset[tuple[str, str]] = frozenset(
    {
        ("huggingface_agents_langgraph.preprocessing", "preprocessing"),
        ("huggingface_agents_langgraph.attachments", "attachment_resolver"),
        ("huggingface_agents_langgraph.routing", "router"),
        ("huggingface_agents_langgraph.code_processing", "code_processing"),
        (
            "huggingface_agents_langgraph.spreadsheet_processing",
            "spreadsheet_processing",
        ),
        (
            "huggingface_agents_langgraph.document_processing",
            "document_processing",
        ),
        (
            "huggingface_agents_langgraph.multimedia_processing",
            "multimedia_processing",
        ),
        ("huggingface_agents_langgraph.web_research", "web_research"),
        ("huggingface_agents_langgraph.research", "review"),
        ("huggingface_agents_langgraph.research", "research_action"),
        ("huggingface_agents_langgraph.reasoning", "reasoning"),
        (
            "huggingface_agents_langgraph.answer_production",
            "answer_production",
        ),
    }
)


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


def create_gaia_v3_registry() -> NodeRegistry:
    """Create a registry pre-loaded with canonical V3.1 node contracts.

    Contracts describe the effective, observable behavior of nodes compiled
    in graph.py, considering recovery wrappers (_recover_acquisition) and
    tracing wrappers.
    """
    registry = NodeRegistry()

    # Preprocessing
    registry.register(
        "preprocessing",
        metadata={"category": "input"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            guaranteed_outputs=frozenset({"question"}),
        ),
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.preprocessing", "preprocessing"
        ),
        description="Normalizes whitespace and prepares question string.",
    )

    # Attachment Resolver
    registry.register(
        "attachment_resolver",
        metadata={"category": "input"},
        contract=NodeContract(
            required_inputs=frozenset({"file_name"}),
            optional_inputs=frozenset({"task_id"}),
            guaranteed_outputs=frozenset({"file_path"}),
        ),
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.attachments", "attachment_resolver"
        ),
        description="Resolves and verifies physical existence of attachment.",
    )

    # Router
    registry.register(
        "router",
        metadata={"category": "input"},
        contract=NodeContract(
            required_inputs=frozenset({"question", "file_name"}),
            optional_inputs=frozenset({"file_path"}),
            guaranteed_outputs=frozenset({"route"}),
        ),
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.routing", "router"
        ),
        description="Deterministic extension-based router with LLM fallback.",
    )

    # Acquisition Nodes (Wrapped by _recover_acquisition in graph.py):
    # If acquisition succeeds, produces evidence. If it raises an error,
    # the wrapper catches it and returns research_notes without evidence.
    # Therefore neither output is unconditionally guaranteed on its own.
    acquisition_contract = NodeContract(
        required_inputs=frozenset({"question", "file_path"}),
        guaranteed_outputs=frozenset(),
        optional_outputs=frozenset({"evidence", "research_notes"}),
    )

    # Code Processing
    registry.register(
        "code_processing",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=acquisition_contract,
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.code_processing", "code_processing"
        ),
        description="Static inspection or sandboxed execution of Python code.",
    )

    # Spreadsheet Processing
    registry.register(
        "spreadsheet_processing",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=acquisition_contract,
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.spreadsheet_processing",
            "spreadsheet_processing",
        ),
        description="Tabular data extraction and structured analysis.",
    )

    # Document Processing
    registry.register(
        "document_processing",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=acquisition_contract,
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.document_processing",
            "document_processing",
        ),
        description="PDF text extraction with relevance filtering.",
    )

    # Multimedia Processing
    registry.register(
        "multimedia_processing",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=acquisition_contract,
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.multimedia_processing",
            "multimedia_processing",
        ),
        description="Audio transcription, sound classification, and VLM inspection.",
    )

    # Web Research (file_path is optional)
    registry.register(
        "web_research",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            optional_inputs=frozenset({"file_path"}),
            guaranteed_outputs=frozenset(),
            optional_outputs=frozenset({"evidence", "research_notes"}),
        ),
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.web_research", "web_research"
        ),
        description="Search engine and encyclopedia retrieval.",
    )

    # Review
    registry.register(
        "review",
        metadata={"category": "research"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            optional_inputs=frozenset(
                {"evidence", "research_action", "action_history", "research_steps"}
            ),
            guaranteed_outputs=frozenset({"research_action"}),
            optional_outputs=frozenset({"research_notes"}),
        ),
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.research", "review"
        ),
        description="Iterative review loop deciding the next research action.",
    )

    # Research Action
    registry.register(
        "research_action",
        metadata={"category": "research"},
        contract=NodeContract(
            required_inputs=frozenset({"question", "research_action"}),
            optional_inputs=frozenset({"evidence", "action_history", "research_steps"}),
            guaranteed_outputs=frozenset(
                {
                    "evidence",
                    "action_history",
                    "research_steps",
                    "research_notes",
                }
            ),
            optional_outputs=frozenset({"source_links"}),
        ),
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.research", "research_action"
        ),
        description="Dispatches and executes the action chosen by the review node.",
    )

    # Reasoning
    registry.register(
        "reasoning",
        metadata={"category": "reasoning"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            optional_inputs=frozenset({"evidence", "research_notes"}),
            guaranteed_outputs=frozenset({"draft_answer"}),
            optional_outputs=frozenset({"reasoning_warnings"}),
        ),
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.reasoning", "reasoning"
        ),
        description="Synthesizes evidence to produce a reasoning draft answer.",
    )

    # Answer Production
    registry.register(
        "answer_production",
        metadata={"category": "output"},
        contract=NodeContract(
            required_inputs=frozenset({"question", "draft_answer"}),
            guaranteed_outputs=frozenset({"submitted_answer", "answer_warnings"}),
            optional_outputs=frozenset(),
        ),
        resolver=lambda: _resolve_module_attr(
            "huggingface_agents_langgraph.answer_production",
            "answer_production",
        ),
        description="Formats concise final answer adhering to GAIA conventions.",
    )

    return registry


def _resolve_module_attr(module_name: str, attr_name: str) -> Callable[..., Any]:
    """Safe internal resolver for pre-approved internal node functions only.

    NOTE: Resolving these base functions directly provides the pure node callables,
    not the recovery and tracing wrappers (_recover_acquisition, traced_node) applied
    in graph.py.
    """
    import importlib

    if (module_name, attr_name) not in AUTHORIZED_CALLABLES:
        raise PermissionError(
            "Unauthorized module attribute resolution attempt: "
            f"'{module_name}.{attr_name}'"
        )
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)
