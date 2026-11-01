"""Immutable, versioned persistence of declarative agent architectures.

A version is identified by the SHA-256 of its canonical definition, so saving the
same content twice returns the existing version. Drafts that fail validation are
stored too; validation is computed on read so it never goes stale.
"""

import hashlib
import json
import math
import threading
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_OID, UUID, uuid5

from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    Diagnostic,
    GraphValidator,
    ValidationReport,
)
from huggingface_agents_langgraph.graph_definition.catalog import build_catalog
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.graph_definition.registry import (
    create_studio_registry,
)
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    create_studio_routing_registry,
)
from huggingface_agents_langgraph.run_tracking import (
    list_records,
    read_record,
    write_record,
)
from huggingface_agents_langgraph.state import AgentState

KIND = "architectures"
LAYOUT_KIND = "layouts"
MAX_LAYOUT_NODES = 500
MAX_LAYOUT_COORDINATE = 1_000_000
BUILTIN_V31_ID = "builtin:gaia_v31"
_SAVE_LOCK = threading.Lock()


class ArchitectureNotFoundError(LookupError):
    """Raised when an architecture version does not exist."""


def content_sha256(definition: AgentDefinition) -> str:
    """Hash the canonical JSON form of a definition."""
    canonical = json.dumps(
        definition.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _builtin_definition() -> AgentDefinition:
    return create_gaia_v31_definition()


def _version_id(digest: str) -> str:
    return str(uuid5(NAMESPACE_OID, digest))


def _summary(record: dict) -> dict:
    keys = (
        "id",
        "architecture_id",
        "version",
        "parent_id",
        "content_sha256",
        "created_at",
        "read_only",
    )
    return {key: record.get(key) for key in keys}


def _builtin_record() -> dict:
    definition = _builtin_definition()
    return {
        "id": BUILTIN_V31_ID,
        "architecture_id": definition.architecture_id,
        "version": None,
        "parent_id": None,
        "content_sha256": content_sha256(definition),
        "created_at": None,
        "read_only": True,
        "definition": definition.to_dict(),
    }


def _saved_records() -> list[dict]:
    return list_records(KIND)


def save_architecture(definition: AgentDefinition) -> dict:
    """Persist a definition as a new immutable version, or return the existing one."""
    if definition.architecture_id == _builtin_definition().architecture_id:
        raise ValueError(
            f"Architecture id '{definition.architecture_id}' is reserved "
            "for the built-in pipeline"
        )
    digest = content_sha256(definition)
    version_id = _version_id(digest)
    with _SAVE_LOCK:
        try:
            return read_record(KIND, version_id)
        except FileNotFoundError:
            pass
        siblings = [
            record
            for record in _saved_records()
            if record["architecture_id"] == definition.architecture_id
        ]
        latest = max(siblings, key=lambda record: record["version"], default=None)
        record = {
            "id": version_id,
            "architecture_id": definition.architecture_id,
            "version": latest["version"] + 1 if latest else 1,
            "parent_id": latest["id"] if latest else None,
            "content_sha256": digest,
            "created_at": datetime.now(UTC).isoformat(),
            "read_only": False,
            "definition": definition.to_dict(),
        }
        write_record(KIND, record)
        return record


def get_architecture(identifier: str) -> dict:
    """Return a stored version, or the built-in V3.1 pipeline."""
    if identifier == BUILTIN_V31_ID:
        return _builtin_record()
    try:
        return read_record(KIND, str(UUID(identifier)))
    except (ValueError, FileNotFoundError) as error:
        raise ArchitectureNotFoundError(identifier) from error


def list_architectures() -> list[dict]:
    """Summaries without definitions: the built-in first, then saved versions."""
    saved = sorted(_saved_records(), key=lambda r: (r["architecture_id"], r["version"]))
    return [_summary(_builtin_record()), *(_summary(record) for record in saved)]


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


def _layout_record_id(version_id: str) -> str:
    return str(uuid5(NAMESPACE_OID, f"layout:{version_id}"))


def _is_coordinate(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and abs(value) <= MAX_LAYOUT_COORDINATE
    )


def _validated_layout(layout: object, node_ids: set[str]) -> dict:
    if not isinstance(layout, dict) or set(layout) != {"nodes"}:
        raise ValueError("layout must be an object with a single 'nodes' key")
    nodes = layout["nodes"]
    if not isinstance(nodes, dict) or len(nodes) > MAX_LAYOUT_NODES:
        raise ValueError("layout nodes must be an object of limited size")
    for node_id, position in nodes.items():
        if node_id not in node_ids:
            raise ValueError(f"layout references unknown node '{node_id}'")
        if (
            not isinstance(position, dict)
            or set(position) != {"x", "y"}
            or not all(_is_coordinate(position[axis]) for axis in ("x", "y"))
        ):
            raise ValueError(
                f"layout position of '{node_id}' needs finite numeric x and y"
            )
    return {"nodes": {k: {"x": v["x"], "y": v["y"]} for k, v in nodes.items()}}


def get_layout(version_id: str) -> dict:
    """Node positions of a version; empty when none were stored yet."""
    get_architecture(version_id)
    try:
        record = read_record(LAYOUT_KIND, _layout_record_id(version_id))
    except FileNotFoundError:
        return {
            "architecture_version_id": version_id,
            "layout": {"nodes": {}},
            "updated_at": None,
        }
    return {
        "architecture_version_id": version_id,
        "layout": record["layout"],
        "updated_at": record["updated_at"],
    }


def save_layout(version_id: str, layout: object) -> dict:
    """Store node positions for a version without altering its identity."""
    definition = get_architecture(version_id)["definition"]
    node_ids = {node["id"] for node in definition["nodes"]}
    validated = _validated_layout(layout, node_ids)
    record = {
        "id": _layout_record_id(version_id),
        "architecture_version_id": version_id,
        "layout": validated,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    write_record(LAYOUT_KIND, record)
    return get_layout(version_id)
