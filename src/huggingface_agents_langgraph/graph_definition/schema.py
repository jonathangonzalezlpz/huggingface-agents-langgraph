"""Declarative, serializable schema definitions for agent architectures.

Defines the structure of agents, nodes, and edges without executing logic,
binding LLM models, or requiring runtime infrastructure.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

SPECIAL_TERMINALS = {"__start__", "__end__", "START", "END"}
START_TERMINALS = {"__start__", "START"}


def _freeze_metadata(data: Mapping[str, Any]) -> MappingProxyType:
    """Validate JSON compatibility and recursively freeze mappings/sequences."""
    try:
        json.dumps(dict(data), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as err:
        raise ValueError(f"Metadata must be JSON-serializable: {err}") from err

    def _freeze(value: Any) -> Any:
        if isinstance(value, Mapping):
            return MappingProxyType({k: _freeze(v) for k, v in value.items()})
        if isinstance(value, (list, tuple)):
            return tuple(_freeze(v) for v in value)
        return value

    return MappingProxyType({k: _freeze(v) for k, v in data.items()})


def _unfreeze_metadata(data: Mapping[str, Any]) -> dict[str, Any]:
    """Convert frozen mapping proxy and tuples back to regular dicts and lists."""

    def _unfreeze(value: Any) -> Any:
        if isinstance(value, (Mapping, MappingProxyType)):
            return {k: _unfreeze(v) for k, v in value.items()}
        if isinstance(value, tuple):
            return [_unfreeze(v) for v in value]
        return value

    return {k: _unfreeze(v) for k, v in data.items()}


@dataclass(frozen=True)
class EdgeDefinition:
    """Represents a connection between nodes, either direct or conditional."""

    source: str
    target: str | None = None
    edge_type: Literal["direct", "conditional"] = "direct"
    routing_strategy: str | None = None
    conditional_targets: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source or not self.source.strip():
            raise ValueError("Edge source cannot be empty")

        if self.edge_type == "direct":
            if not self.target or not self.target.strip():
                raise ValueError(
                    f"Direct edge from '{self.source}' must have a valid target"
                )
            if self.routing_strategy is not None or self.conditional_targets:
                raise ValueError(
                    f"Direct edge from '{self.source}' cannot have "
                    "routing_strategy or conditional_targets"
                )
        elif self.edge_type == "conditional":
            if self.target is not None:
                raise ValueError(
                    f"Conditional edge from '{self.source}' must not specify "
                    "a direct target"
                )
            if not self.routing_strategy or not self.routing_strategy.strip():
                raise ValueError(
                    f"Conditional edge from '{self.source}' must specify "
                    "a routing_strategy identifier"
                )
            if not self.conditional_targets:
                raise ValueError(
                    f"Conditional edge from '{self.source}' must declare "
                    "at least one conditional target"
                )
            for branch in self.conditional_targets:
                if not isinstance(branch, str) or not branch.strip():
                    raise ValueError(
                        f"Conditional edge from '{self.source}' has an empty "
                        f"branch key: {branch!r}"
                    )
            # Ensure conditional_targets is an immutable mapping proxy
            object.__setattr__(
                self,
                "conditional_targets",
                MappingProxyType(dict(self.conditional_targets)),
            )
        else:
            raise ValueError(
                f"Invalid edge_type '{self.edge_type}', "
                "must be 'direct' or 'conditional'"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize edge to a plain dictionary."""
        data: dict[str, Any] = {
            "source": self.source,
            "edge_type": self.edge_type,
        }
        if self.edge_type == "direct":
            data["target"] = self.target
        else:
            data["routing_strategy"] = self.routing_strategy
            data["conditional_targets"] = dict(self.conditional_targets)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EdgeDefinition":
        """Deserialize edge from a dictionary."""
        edge_type = data.get("edge_type", "direct")
        return cls(
            source=data["source"],
            target=data.get("target"),
            edge_type=edge_type,
            routing_strategy=data.get("routing_strategy"),
            conditional_targets=dict(data.get("conditional_targets", {})),
        )


@dataclass(frozen=True)
class NodeDefinition:
    """Declarative node representation inside an agent architecture."""

    id: str
    implementation_id: str
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # Values for the parameters the component declares; plain JSON, never code.
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("Node id cannot be empty")
        if self.id in SPECIAL_TERMINALS:
            raise ValueError(f"Node id cannot use reserved terminal name '{self.id}'")
        if not self.implementation_id or not self.implementation_id.strip():
            raise ValueError(
                f"Node '{self.id}' must reference a non-empty implementation_id"
            )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        object.__setattr__(self, "params", _freeze_metadata(self.params))

    def to_dict(self) -> dict[str, Any]:
        """Serialize node definition to a plain dictionary.

        ``params`` is written only when present, so definitions saved before
        parameters existed keep exactly the same content and hash.
        """
        data: dict[str, Any] = {
            "id": self.id,
            "implementation_id": self.implementation_id,
            "description": self.description,
            "metadata": _unfreeze_metadata(self.metadata),
        }
        if self.params:
            data["params"] = _unfreeze_metadata(self.params)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeDefinition":
        """Deserialize node definition from a dictionary."""
        return cls(
            id=data["id"],
            implementation_id=data["implementation_id"],
            description=data.get("description", ""),
            metadata=dict(data.get("metadata", {})),
            params=dict(data.get("params", {})),
        )


@dataclass(frozen=True)
class AgentDefinition:
    """Fully declarative, serializable, and versioned agent architecture."""

    schema_version: str
    architecture_id: str
    state_type: str
    initial_node: str
    nodes: tuple[NodeDefinition, ...] = field(default_factory=tuple)
    edges: tuple[EdgeDefinition, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.schema_version or not self.schema_version.strip():
            raise ValueError("AgentDefinition schema_version cannot be empty")
        if not self.architecture_id or not self.architecture_id.strip():
            raise ValueError("AgentDefinition architecture_id cannot be empty")
        if not self.state_type or not self.state_type.strip():
            raise ValueError("AgentDefinition state_type cannot be empty")
        if not self.initial_node or not self.initial_node.strip():
            raise ValueError("AgentDefinition initial_node cannot be empty")

        # Convert sequences to tuples for immutability
        nodes_tuple = tuple(self.nodes)
        edges_tuple = tuple(self.edges)
        object.__setattr__(self, "nodes", nodes_tuple)
        object.__setattr__(self, "edges", edges_tuple)
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

        # Check for duplicate node IDs
        node_ids: set[str] = set()
        for node in nodes_tuple:
            if node.id in node_ids:
                raise ValueError(
                    f"Duplicate node id detected in AgentDefinition: '{node.id}'"
                )
            node_ids.add(node.id)

        if self.initial_node not in node_ids:
            declared = sorted(node_ids)
            raise ValueError(
                f"initial_node '{self.initial_node}' does not match any "
                f"declared node: {declared}"
            )

        # Validate edge endpoints
        valid_sources = node_ids | START_TERMINALS
        valid_targets = node_ids | (SPECIAL_TERMINALS - START_TERMINALS)

        for edge in edges_tuple:
            if edge.source not in valid_sources:
                declared = sorted(node_ids)
                raise ValueError(
                    f"Edge source '{edge.source}' does not match any "
                    f"declared node: {declared}"
                )
            if edge.edge_type == "direct":
                if edge.target in START_TERMINALS:
                    raise ValueError(f"Edge from '{edge.source}' cannot target START")
                if edge.target not in valid_targets:
                    valid_str = sorted(valid_targets)
                    raise ValueError(
                        f"Direct edge target '{edge.target}' does not match "
                        f"any declared node or terminal: {valid_str}"
                    )
            elif edge.edge_type == "conditional":
                for branch, branch_target in edge.conditional_targets.items():
                    if branch_target in START_TERMINALS:
                        raise ValueError(
                            f"Conditional edge branch '{branch}' cannot target START"
                        )
                    if branch_target not in valid_targets:
                        valid_str = sorted(valid_targets)
                        raise ValueError(
                            f"Conditional edge branch '{branch}' target "
                            f"'{branch_target}' does not match any declared "
                            f"node or terminal: {valid_str}"
                        )

    def get_node(self, node_id: str) -> NodeDefinition | None:
        """Find a node definition by its ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize agent definition to a plain dictionary."""
        return {
            "schema_version": self.schema_version,
            "architecture_id": self.architecture_id,
            "state_type": self.state_type,
            "initial_node": self.initial_node,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": _unfreeze_metadata(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentDefinition":
        """Deserialize agent definition from a dictionary."""
        return cls(
            schema_version=data["schema_version"],
            architecture_id=data["architecture_id"],
            state_type=data["state_type"],
            initial_node=data["initial_node"],
            nodes=tuple(NodeDefinition.from_dict(n) for n in data.get("nodes", [])),
            edges=tuple(EdgeDefinition.from_dict(e) for e in data.get("edges", [])),
            metadata=dict(data.get("metadata", {})),
        )
