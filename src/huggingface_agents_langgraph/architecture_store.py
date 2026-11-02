"""Immutable, versioned persistence of declarative agent architectures.

A version is identified by the SHA-256 of its canonical definition, so saving the
same content twice returns the existing version. Drafts that fail validation are
stored too; validation is computed on read (see ``architecture_service``) so it
never goes stale.
"""

import hashlib
import json
import threading
from datetime import UTC, datetime
from uuid import NAMESPACE_OID, UUID, uuid5

from huggingface_agents_langgraph.graph_definition import AgentDefinition
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.run_tracking import (
    list_records,
    read_record,
    write_record,
)

KIND = "architectures"
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
