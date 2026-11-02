"""Where each node of an architecture version sits on the canvas.

A layout is mutable and stored apart from the version, so moving a node never
changes the version's content hash.
"""

import math
from datetime import UTC, datetime
from uuid import NAMESPACE_OID, uuid5

from huggingface_agents_langgraph.adapters.records import read_record, write_record
from huggingface_agents_langgraph.application.architecture_store import get_architecture

LAYOUT_KIND = "layouts"
MAX_LAYOUT_NODES = 500
MAX_LAYOUT_COORDINATE = 1_000_000


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
