"""Local JSON persistence of runs, experiments, architectures and layouts."""

import json
from pathlib import Path
from uuid import UUID, uuid4

from huggingface_agents_langgraph.config import RUNTIME_DIRECTORY
from huggingface_agents_langgraph.pipeline_versions import V2_REFERENCE_ID


def write_record(kind: str, record: dict) -> None:
    """Atomically store a record under its UUID in the runtime directory."""
    record_id = str(UUID(record["id"]))
    directory = Path(RUNTIME_DIRECTORY) / kind
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{record_id}.json"
    if kind == "experiments" and record_id == V2_REFERENCE_ID and destination.exists():
        original = json.loads(destination.read_text(encoding="utf-8"))
        if any(record.get(key) != value for key, value in original.items()):
            raise ValueError("The V2 reference is immutable; save a new experiment")
        return
    temporary = directory / f".{record_id}.{uuid4()}.tmp"
    temporary.write_text(
        json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8"
    )
    temporary.replace(destination)


def read_record(kind: str, record_id: str) -> dict:
    """Load a UUID-addressed runtime record."""
    path = Path(RUNTIME_DIRECTORY) / kind / f"{UUID(record_id)}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_records(kind: str) -> list[dict]:
    """Load locally persisted records, newest first."""
    directory = Path(RUNTIME_DIRECTORY) / kind
    records = []
    for path in directory.glob("*.json"):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)


def delete_record(kind: str, record_id: str) -> None:
    """Delete only the selected UUID-addressed record."""
    if kind == "experiments" and str(UUID(record_id)) == V2_REFERENCE_ID:
        raise ValueError("The V2 reference cannot be deleted from the experiment panel")
    (Path(RUNTIME_DIRECTORY) / kind / f"{UUID(record_id)}.json").unlink(missing_ok=True)
